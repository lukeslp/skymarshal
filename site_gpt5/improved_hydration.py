#!/usr/bin/env python3
"""
Improved engagement hydration for Bluesky posts using public AppView endpoints.
- Robust retries with exponential backoff
- Short HTTP timeouts to avoid hangs
- Accurate pagination for likes/reposts/quotes
- Thread traversal for replies

Public endpoints used (no auth required):
- app.bsky.feed.getPosts
- app.bsky.feed.getLikes
- app.bsky.feed.getRepostedBy
- app.bsky.feed.getQuotes
- app.bsky.feed.getPostThread
"""
from __future__ import annotations

import time
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

from batch_processor import create_standard_batch_processor, BlueskyBatchProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APPVIEW = "https://public.api.bsky.app/xrpc"


@dataclass
class PostEngagement:
    uri: str
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    engagement_score: float = 0.0


class BlueskyEngagementHydrator:
    def __init__(self, client=None, rate_limit_delay: float = 0.4, max_retries: int = 3):
        self.client = client
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Skymarshal/EngagementHydrator",
            "Accept": "application/json",
        })

    def _make_request(self, path: str, params: Dict[str, Any], timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        url = f"{APPVIEW}/{path}"
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.rate_limit_delay)
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 429:
                    wait_time = min(2 ** attempt, 8)
                    logger.warning(f"Rate limited ({path}), waiting {wait_time}s (attempt {attempt+1})")
                    time.sleep(wait_time)
                    continue
                logger.warning(f"HTTP {r.status_code} {path}")
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout {path} (attempt {attempt+1})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error {path}: {e}")
            if attempt < self.max_retries - 1:
                time.sleep(min(2 ** attempt, 4))
        return None

    def get_post_details(self, uris: List[str]) -> Dict[str, PostEngagement]:
        """Get post details using optimized 25-item batch processing."""
        if not uris:
            return {}
        
        # Use the new batch processor for consistent 25-item batching
        batch_processor = create_standard_batch_processor(self.client)
        batch_result = batch_processor.batch_get_posts(uris)
        
        # Convert batch results to PostEngagement objects
        results: Dict[str, PostEngagement] = {}
        for post_data_list in batch_result.results:
            if isinstance(post_data_list, list):
                for post_data in post_data_list:
                    uri = post_data.get('uri')
                    if uri:
                        results[uri] = PostEngagement(
                            uri=uri,
                            like_count=post_data.get('like_count', 0),
                            repost_count=post_data.get('repost_count', 0),
                            reply_count=post_data.get('reply_count', 0),
                        )
        
        logger.info(f"Batch processed {len(uris)} URIs, got {len(results)} results "
                   f"({batch_result.success_rate:.1f}% success rate)")
        
        return results

    def _count_paginated(self, path: str, base_params: Dict[str, Any], items_key: str, max_pages: int = 50) -> int:
        total = 0
        cursor: Optional[str] = None
        pages = 0
        while pages < max_pages:
            params = dict(base_params)
            params["limit"] = 100
            if cursor:
                params["cursor"] = cursor
            data = self._make_request(path, params)
            if not data or items_key not in data:
                break
            items = data.get(items_key, []) or []
            total += len(items)
            cursor = data.get("cursor")
            if not cursor:
                break
            pages += 1
        return total

    def _count_thread_replies(self, uri: str, depth: int = 1) -> int:
        data = self._make_request(
            "app.bsky.feed.getPostThread", {"uri": uri, "depth": depth, "parentHeight": 0}
        )
        if not data or "thread" not in data:
            return 0

        def walk(node: Dict[str, Any]) -> int:
            cnt = 0
            for r in node.get("replies", []) or []:
                if r.get("post"):
                    cnt += 1
                cnt += walk(r)
            return cnt

        return walk(data["thread"])

    def get_detailed_engagement(self, uri: str) -> PostEngagement:
        pe = PostEngagement(uri=uri)
        # Likes
        pe.like_count = self._count_paginated("app.bsky.feed.getLikes", {"uri": uri}, "likes")
        # Reposts
        pe.repost_count = self._count_paginated("app.bsky.feed.getRepostedBy", {"uri": uri}, "repostedBy")
        # Quotes
        pe.quote_count = self._count_paginated("app.bsky.feed.getQuotes", {"uri": uri}, "posts")
        # Replies
        pe.reply_count = self._count_thread_replies(uri, depth=1)
        # Score (weights): 1 + 3 + 5 + 4
        pe.engagement_score = round(
            (pe.like_count * 1.0)
            + (pe.repost_count * 3.0)
            + (pe.reply_count * 5.0)
            + (pe.quote_count * 4.0),
            2,
        )
        return pe

    def hydrate_posts_batch(self, posts: List[Any], detailed: bool = False) -> Dict[str, PostEngagement]:
        uris = []
        for p in posts:
            uri = getattr(p, "uri", None)
            if uri and getattr(p, "content_type", "") in ("post", "reply"):
                uris.append(uri)
        if not uris:
            return {}

        logger.info(f"Hydrating {len(uris)} posts (detailed={detailed})")

        if detailed:
            out: Dict[str, PostEngagement] = {}
            for uri in uris:
                try:
                    pe = self.get_detailed_engagement(uri)
                    out[uri] = pe
                    logger.info(
                        f"Hydrated {uri}: {pe.like_count}L {pe.repost_count}R {pe.reply_count}Rep {pe.quote_count}Q"
                    )
                except Exception as e:
                    logger.warning(f"Detailed hydrate failed for {uri}: {e}")
            return out
        else:
            return self.get_post_details(uris)


def update_post_objects(posts: List[Any], engagement_data: Dict[str, PostEngagement]) -> None:
    for p in posts:
        uri = getattr(p, "uri", None)
        if not uri:
            continue
        pe = engagement_data.get(uri)
        if not pe:
            continue
        p.like_count = int(pe.like_count)
        p.repost_count = int(pe.repost_count)
        p.reply_count = int(pe.reply_count)
        if hasattr(p, "quote_count"):
            setattr(p, "quote_count", int(pe.quote_count))
        # Update engagement score if available; otherwise compute
        if hasattr(p, "engagement_score"):
            try:
                p.engagement_score = float(pe.engagement_score)
            except Exception:
                pass
        if hasattr(p, "update_engagement_score"):
            try:
                p.update_engagement_score()
            except Exception:
                pass


def hydrate_bluesky_posts(posts: List[Any], client=None, detailed: bool = False) -> Dict[str, PostEngagement]:
    hydrator = BlueskyEngagementHydrator(client=client)
    data = hydrator.hydrate_posts_batch(posts, detailed=detailed)
    update_post_objects(posts, data)
    return data
