"""Feature extraction for Bluesky posts.

Ported from firehose/server/sentiment.ts extractFeatures().
Extracts hashtags, mentions, URLs, media info, language, word count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
