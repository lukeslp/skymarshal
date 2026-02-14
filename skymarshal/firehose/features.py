"""Feature extraction for Bluesky posts.

Ported from firehose/server/sentiment.ts extractFeatures().
Extracts hashtags, mentions, URLs, media info, language, word count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MediaInfo:
    """Media information extracted from AT Protocol embeds."""
    image_urls: List[str] = field(default_factory=list)
    video_thumb_url: Optional[str] = None
    video_playlist_url: Optional[str] = None
    external_url: Optional[str] = None
    external_title: Optional[str] = None
    external_description: Optional[str] = None
    external_thumb_url: Optional[str] = None


@dataclass
class PostFeatures:
    char_count: int = 0
    word_count: int = 0
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    language: str = "unknown"
    has_images: bool = False
    has_video: bool = False
    has_link: bool = False
    is_quote: bool = False
    quote_uri: Optional[str] = None
    is_reply: bool = False
    media: MediaInfo = field(default_factory=MediaInfo)


# Regex patterns
_HASHTAG_RE = re.compile(r"#[\w\u0080-\uFFFF]+")
_MENTION_RE = re.compile(r"@[\w.]+")
_URL_RE = re.compile(r"https?://\S+")


def extract_features(text: str, record: Optional[Dict[str, Any]] = None) -> PostFeatures:
    """Extract linguistic and structural features from a Bluesky post.

    Args:
        text: Post text content.
        record: Optional AT Protocol record with facets, langs, embed, reply.

    Returns:
        PostFeatures dataclass with all extracted features.
    """
    record = record or {}
    features = PostFeatures()

    # Character and word count
    features.char_count = len(text)
    features.word_count = len([w for w in text.split() if w])

    # Hashtags — prefer structured facets, fallback to regex
    if record.get("facets"):
        for facet in record["facets"]:
            for feature in facet.get("features", []):
                if feature.get("$type") == "app.bsky.richtext.facet#tag":
                    tag = feature.get("tag", "")
                    if tag:
                        features.hashtags.append(f"#{tag}")

    if not features.hashtags:
        features.hashtags = _HASHTAG_RE.findall(text)

    # Mentions
    features.mentions = _MENTION_RE.findall(text)

    # URLs
    features.links = _URL_RE.findall(text)

    # Language from record metadata
    langs = record.get("langs")
    if isinstance(langs, list) and langs:
        features.language = langs[0]

    # Media and embeds
    embed = record.get("embed", {})
    embed_type = embed.get("$type", "") if isinstance(embed, dict) else ""

    features.has_images = "images" in embed_type
    features.has_video = "video" in embed_type
    features.has_link = "external" in embed_type or bool(features.links)

    # Extract media URLs based on embed type
    if embed_type == "app.bsky.embed.images":
        # Images embed: extract all image URLs
        images = embed.get("images", [])
        for img in images:
            if isinstance(img, dict) and "image" in img:
                img_obj = img["image"]
                if isinstance(img_obj, dict):
                    # Can be either a blob ref or a string URL
                    ref = img_obj.get("ref") or img_obj.get("$link")
                    if ref:
                        # Construct CDN URL from blob reference
                        features.media.image_urls.append(f"https://cdn.bsky.app/img/feed_thumbnail/plain/{record.get('$did', '')}/{ref}")

    elif embed_type == "app.bsky.embed.video":
        # Video embed: extract thumbnail and playlist URL
        video = embed.get("video", {})
        if isinstance(video, dict):
            thumb = video.get("thumbnail")
            if isinstance(thumb, dict):
                ref = thumb.get("ref") or thumb.get("$link")
                if ref:
                    features.media.video_thumb_url = f"https://cdn.bsky.app/img/feed_thumbnail/plain/{record.get('$did', '')}/{ref}"
            # Video playlist URL (if available in record)
            ref = video.get("ref") or video.get("$link")
            if ref:
                features.media.video_playlist_url = f"https://video.bsky.app/watch/{ref}/playlist.m3u8"

    elif embed_type == "app.bsky.embed.external":
        # External link embed: extract URL and metadata
        external = embed.get("external", {})
        if isinstance(external, dict):
            features.media.external_url = external.get("uri")
            features.media.external_title = external.get("title")
            features.media.external_description = external.get("description")
            thumb = external.get("thumb")
            if isinstance(thumb, dict):
                ref = thumb.get("ref") or thumb.get("$link")
                if ref:
                    features.media.external_thumb_url = f"https://cdn.bsky.app/img/feed_thumbnail/plain/{record.get('$did', '')}/{ref}"

    elif embed_type == "app.bsky.embed.recordWithMedia":
        # Quote post with media: extract media from nested embed
        media_embed = embed.get("media", {})
        media_type = media_embed.get("$type", "")

        if media_type == "app.bsky.embed.images":
            images = media_embed.get("images", [])
            for img in images:
                if isinstance(img, dict) and "image" in img:
                    img_obj = img["image"]
                    if isinstance(img_obj, dict):
                        ref = img_obj.get("ref") or img_obj.get("$link")
                        if ref:
                            features.media.image_urls.append(f"https://cdn.bsky.app/img/feed_thumbnail/plain/{record.get('$did', '')}/{ref}")

        elif media_type == "app.bsky.embed.external":
            external = media_embed.get("external", {})
            if isinstance(external, dict):
                features.media.external_url = external.get("uri")
                features.media.external_title = external.get("title")
                features.media.external_description = external.get("description")
                thumb = external.get("thumb")
                if isinstance(thumb, dict):
                    ref = thumb.get("ref") or thumb.get("$link")
                    if ref:
                        features.media.external_thumb_url = f"https://cdn.bsky.app/img/feed_thumbnail/plain/{record.get('$did', '')}/{ref}"

    # Quote detection
    if embed_type == "app.bsky.embed.record":
        features.is_quote = True
        features.quote_uri = (embed.get("record") or {}).get("uri")
    elif embed_type == "app.bsky.embed.recordWithMedia":
        features.is_quote = True
        inner_record = (embed.get("record") or {}).get("record") or {}
        features.quote_uri = inner_record.get("uri")

    # Reply detection
    features.is_reply = bool(record.get("reply"))

    return features
