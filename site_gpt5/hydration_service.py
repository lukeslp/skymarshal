#!/usr/bin/env python3
"""
Hydration service for breaking down the large _web_safe_hydrate function.

This module provides a more organized approach to engagement hydration
by separating concerns and making the code more testable and maintainable.
"""
from __future__ import annotations

import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from utils import HydrationConfig, create_bluesky_client, safe_getattr, retry_with_backoff
from batch_processor import create_standard_batch_processor, create_conservative_batch_processor

try:
    from atproto import Client as ATClient
    from atproto import models as ATModels
except Exception:
    ATClient = None  # type: ignore
    ATModels = None  # type: ignore

try:
    from skymarshal.auth import AuthManager
    from skymarshal.data_manager import DataManager
    from skymarshal.models import UserSettings
except Exception:
    # For testing without full Skymarshal dependency
    AuthManager = None  # type: ignore
    DataManager = None  # type: ignore
    UserSettings = None  # type: ignore


@dataclass
class HydrationResult:
    """Result of hydration operation."""
    quotes_by_uri: Dict[str, int]
    hydrated_items: List[Any]
    success: bool
    error_message: Optional[str] = None


class SmallDatasetHydrator:
    """Handles hydration for small datasets using exact endpoints."""
    
    def __init__(self, config: HydrationConfig):
        self.config = config
    
    def can_handle(self, items: List[Any]) -> bool:
        """Check if this handler can process the dataset."""
        return len(items) <= self.config.small_dataset_threshold
    
    def hydrate(self, auth: Optional[AuthManager], items: List[Any]) -> Dict[str, int]:
        """Hydrate small dataset using optimized 25-item batch processing."""
        try:
            client = self._get_client(auth)
            if client is None:
                return {}
            
            print(f"DEBUG: Small dataset path - using 25-item batch processing")
            
            # Use standard batch processor for small datasets
            batch_processor = create_standard_batch_processor(client)
            batch_result = batch_processor.batch_hydrate_engagement(items)
            
            print(f"DEBUG: Batch processed {len(items)} items with {batch_result.success_rate:.1f}% success rate")
            
            # Return empty dict for now (exact endpoints would be called separately)
            return {}
            
        except Exception as e:
            print(f"DEBUG: Small dataset batch processing failed: {e}")
            return {}
    
    def _get_client(self, auth: Optional[AuthManager]) -> Optional[ATClient]:
        """Get appropriate client for hydration."""
        if auth and safe_getattr(auth, "client", None) is not None:
            print(f"DEBUG: Using authenticated client")
            return auth.client
        elif ATClient is not None:
            client = create_bluesky_client()
            if client:
                print(f"DEBUG: Using unauthenticated client")
            return client
        else:
            print(f"DEBUG: No client available for small dataset path")
            return None
    
    def _hydrate_exact_endpoints(self, client: ATClient, items: List[Any]) -> Dict[str, int]:
        """Use exact endpoints for precise metrics."""
        # This would call the existing _hydrate_post_edges_exact function
        # For now, return empty dict as placeholder
        return {}


class LargeDatasetHydrator:
    """Handles hydration for large datasets with optimizations."""
    
    def __init__(self, config: HydrationConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Skymarshal/WebHydrator",
            "Accept": "application/json",
        })
    
    def can_handle(self, items: List[Any]) -> bool:
        """Check if this handler can process the dataset."""
        return len(items) > self.config.small_dataset_threshold
    
    def hydrate(
        self, 
        auth: Optional[AuthManager], 
        items: List[Any], 
        settings: UserSettings,
        base: Path,
        cars_dir: Path,
        json_dir: Path
    ) -> Dict[str, int]:
        """Hydrate large dataset with optimizations."""
        deadline = time.time() + self.config.budget_seconds
        
        # Try fast hydrate path if enabled
        if self.config.fast_hydrate:
            self._try_fast_hydrate(auth, items, deadline)
        
        # Use authenticated or unauthenticated path
        if auth and auth.is_authenticated():
            return self._hydrate_authenticated(auth, items, settings, base, cars_dir, json_dir)
        else:
            return self._hydrate_unauthenticated(items)
    
    def _try_fast_hydrate(self, auth: Optional[AuthManager], items: List[Any], deadline: float):
        """Attempt fast hydration using optimized 25-item batch processing."""
        try:
            client = self._get_client(auth)
            if client is None:
                return
            
            print(f"DEBUG: Fast hydrate path - using 25-item batch processor")
            
            # Use fast batch processor (reduced delays)
            from batch_processor import create_fast_batch_processor
            batch_processor = create_fast_batch_processor(client)
            
            # Filter items to only posts and replies
            hydrate_items = [item for item in items 
                           if safe_getattr(item, "content_type", "") in ("post", "reply") 
                           and safe_getattr(item, "uri", None)]
            
            if hydrate_items:
                batch_result = batch_processor.batch_hydrate_engagement(hydrate_items)
                print(f"DEBUG: Fast batch processing: {batch_result.success_count}/{len(hydrate_items)} items "
                      f"({batch_result.success_rate:.1f}% success rate) in {batch_result.processing_time:.2f}s")
                
        except Exception as e:
            print(f"DEBUG: Fast batch processing failed: {e}")
            pass  # Fast path failed, will fall back to regular hydration
    
    def _process_batch(self, client: ATClient, batch: List[str], index: Dict[str, Any]):
        """Process a batch of URIs for fast hydration."""
        posts = []
        
        # Try authenticated client first
        try:
            resp = client.get_posts(uris=batch)
            posts = safe_getattr(resp, "posts", []) or []
        except Exception:
            # Fallback to HTTP request
            try:
                params = [("uris", u) for u in batch]
                r = self.session.get(
                    "https://api.bsky.app/xrpc/app.bsky.feed.getPosts", 
                    params=params, 
                    timeout=self.config.api_timeout
                )
                if r.ok:
                    posts = r.json().get("posts", [])
            except Exception:
                posts = []
        
        # Update items with engagement data
        for p in posts:
            uri = safe_getattr(p, "uri", None) if hasattr(p, "uri") else p.get("uri")
            item = index.get(uri)
            if not item:
                continue
                
            like_v = safe_getattr(p, "like_count", None) if hasattr(p, "like_count") else p.get("likeCount", 0)
            repost_v = safe_getattr(p, "repost_count", None) if hasattr(p, "repost_count") else p.get("repostCount", 0)
            reply_v = safe_getattr(p, "reply_count", None) if hasattr(p, "reply_count") else p.get("replyCount", 0)
            
            item.like_count = int(like_v or 0)
            item.repost_count = int(repost_v or 0)
            item.reply_count = int(reply_v or 0)
            
            if hasattr(item, "update_engagement_score"):
                item.update_engagement_score()
    
    def _get_client(self, auth: Optional[AuthManager]) -> Optional[ATClient]:
        """Get appropriate client for hydration."""
        if auth and safe_getattr(auth, "client", None) is not None:
            return auth.client
        elif ATClient is not None:
            return create_bluesky_client()
        return None
    
    def _hydrate_authenticated(
        self,
        auth: AuthManager,
        items: List[Any],
        settings: UserSettings,
        base: Path,
        cars_dir: Path,
        json_dir: Path
    ) -> Dict[str, int]:
        """Hydrate using authenticated DataManager."""
        if DataManager is None:
            return {}
        
        dm = DataManager(auth, settings, base, cars_dir, json_dir)
        
        # Separate items by type
        pr_items = [it for it in items if safe_getattr(it, "content_type", "") in ("post", "reply")]
        rp_items = ([it for it in items if safe_getattr(it, "content_type", "") == "repost"] 
                   if settings.use_subject_engagement_for_reposts else [])
        
        # Use conservative chunk size
        chunk_size = max(1, min(20, safe_getattr(settings, "hydrate_batch_size", 25)))
        
        # Hydrate posts/replies in chunks
        for i in range(0, len(pr_items), chunk_size):
            chunk = pr_items[i:i + chunk_size]
            self._hydrate_with_retries(
                lambda c=chunk: dm._hydrate_post_engagement(c),  # type: ignore[attr-defined]
                "posts",
                auth,
                settings,
                base,
                cars_dir,
                json_dir
            )
        
        # Hydrate repost subject metrics in chunks
        for i in range(0, len(rp_items), chunk_size):
            chunk = rp_items[i:i + chunk_size]
            self._hydrate_with_retries(
                lambda c=chunk: dm._hydrate_repost_subject_engagement(c),  # type: ignore[attr-defined]
                "reposts",
                auth,
                settings,
                base,
                cars_dir,
                json_dir
            )
        
        # Update engagement scores
        for item in items:
            if hasattr(item, "update_engagement_score"):
                item.update_engagement_score()
        
        # Get client for exact endpoint calls
        client = safe_getattr(dm, "auth", None)
        client = safe_getattr(client, "client", None)
        if client is None and ATClient is not None:
            client = create_bluesky_client()
        
        if client is not None:
            return self._get_exact_quotes(client, items)
        
        return {}
    
    @retry_with_backoff(max_attempts=3)
    def _hydrate_with_retries(
        self,
        hydrate_func: callable,
        chunk_label: str,
        auth: AuthManager,
        settings: UserSettings,
        base: Path,
        cars_dir: Path,
        json_dir: Path
    ):
        """Hydrate with automatic retry and auth recovery."""
        try:
            hydrate_func()
        except Exception as e:
            msg = str(e).lower()
            # Try single-session rebuild on auth errors
            if any(s in msg for s in ("auth", "unauthorized", "token", "expired", "forbidden")):
                # This would implement session recovery logic
                # For now, re-raise the exception
                raise
            else:
                # Re-raise for backoff retry
                raise
    
    def _hydrate_unauthenticated(self, items: List[Any]) -> Dict[str, int]:
        """Hydrate using public endpoints with conservative 20-item batching."""
        if ATClient is None:
            return {}
        
        try:
            client = create_bluesky_client()
            if client is None:
                return {}
            
            print(f"DEBUG: Unauthenticated hydration using conservative batch processor")
            
            # Use conservative batch processor for unauthenticated requests
            batch_processor = create_conservative_batch_processor(client)
            
            # Filter items to posts and replies only
            hydrate_items = [item for item in items 
                           if safe_getattr(item, "content_type", "") in ("post", "reply") 
                           and safe_getattr(item, "uri", None)]
            
            if hydrate_items:
                batch_result = batch_processor.batch_hydrate_engagement(hydrate_items)
                print(f"DEBUG: Conservative batch processing: {batch_result.success_count}/{len(hydrate_items)} items "
                      f"({batch_result.success_rate:.1f}% success rate) in {batch_result.processing_time:.2f}s")
            
            # Return empty dict for now (exact endpoints would be called separately)
            return {}
            
        except Exception as e:
            print(f"DEBUG: Unauthenticated batch processing failed: {e}")
            return {}
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _hydrate_batch_unauthenticated(self, client: ATClient, batch: List[str], index: Dict[str, Any]):
        """Hydrate a batch of items using unauthenticated client."""
        try:
            resp = client.get_posts(uris=batch)
            posts = safe_getattr(resp, "posts", []) or []
            
            for p in posts:
                uri = safe_getattr(p, "uri", None)
                item = index.get(uri)
                if not item:
                    continue
                    
                item.like_count = int(safe_getattr(p, "like_count", 0) or 0)
                item.repost_count = int(safe_getattr(p, "repost_count", 0) or 0)
                item.reply_count = int(safe_getattr(p, "reply_count", 0) or 0)
                
                if hasattr(item, "update_engagement_score"):
                    item.update_engagement_score()
                    
        except Exception as e:
            print(f"DEBUG: Batch hydration failed: {e}")
            raise
    
    def _get_exact_quotes(self, client: ATClient, items: List[Any]) -> Dict[str, int]:
        """Get exact quote counts using precise endpoints."""
        # This would call the existing _hydrate_post_edges_exact function
        # For now, return empty dict as placeholder
        return {}


class HydrationOrchestrator:
    """Main orchestrator for hydration operations."""
    
    def __init__(self, config: Optional[HydrationConfig] = None):
        self.config = config or HydrationConfig()
        self.small_hydrator = SmallDatasetHydrator(self.config)
        self.large_hydrator = LargeDatasetHydrator(self.config)
    
    def hydrate(
        self,
        auth: Optional[AuthManager],
        settings: UserSettings,
        base: Path,
        cars_dir: Path,
        json_dir: Path,
        items: List[Any]
    ) -> Dict[str, int]:
        """
        Orchestrate hydration based on dataset size and available resources.
        
        Args:
            auth: Authentication manager (optional)
            settings: User settings
            base: Base directory path
            cars_dir: CAR files directory
            json_dir: JSON files directory
            items: Items to hydrate
            
        Returns:
            Dictionary mapping URIs to quote counts
        """
        print(f"DEBUG: Starting hydration with {len(items)} items, FAST_HYDRATE={self.config.fast_hydrate}")
        
        # Choose appropriate hydrator based on dataset size
        if self.small_hydrator.can_handle(items):
            return self.small_hydrator.hydrate(auth, items)
        elif self.large_hydrator.can_handle(items):
            return self.large_hydrator.hydrate(auth, items, settings, base, cars_dir, json_dir)
        else:
            print(f"DEBUG: No suitable hydrator for {len(items)} items")
            return {}


# Factory function to maintain compatibility with existing code
def create_hydration_service(
    fast_hydrate: bool = False,
    budget_seconds: float = 10.0
) -> HydrationOrchestrator:
    """Create a hydration service with specified configuration."""
    config = HydrationConfig(
        fast_hydrate=fast_hydrate,
        budget_seconds=budget_seconds
    )
    return HydrationOrchestrator(config)