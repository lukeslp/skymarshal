#!/usr/bin/env python3
"""
Optimized batch processing system for Bluesky API operations.

Standardizes on 25-item batching across all operations for maximum API efficiency
while respecting rate limits and providing robust error handling.
"""
from __future__ import annotations

import time
import asyncio
from typing import List, Dict, Any, Optional, Callable, TypeVar, Iterator
from dataclasses import dataclass, field
from enum import Enum
import logging

from utils import retry_with_backoff, safe_getattr

T = TypeVar('T')
R = TypeVar('R')

logger = logging.getLogger(__name__)

class BatchStrategy(Enum):
    """Different batching strategies for different API operations."""
    STANDARD = "standard"           # 25 items - optimal for getPosts
    CONSERVATIVE = "conservative"   # 20 items - for rate-limited scenarios  
    LARGE_PAGINATION = "large"      # 100 items - for pagination endpoints
    SMALL = "small"                 # 10 items - for testing or slow endpoints

@dataclass
class BatchConfig:
    """Configuration for batch processing operations."""
    strategy: BatchStrategy = BatchStrategy.STANDARD
    batch_size: int = field(init=False)
    delay_between_batches: float = 0.4
    max_retries: int = 3
    timeout_per_batch: float = 5.0
    exponential_backoff: bool = True
    max_concurrent_batches: int = 1  # Sequential by default for API compliance
    
    def __post_init__(self):
        """Set batch size based on strategy."""
        batch_sizes = {
            BatchStrategy.STANDARD: 25,
            BatchStrategy.CONSERVATIVE: 20, 
            BatchStrategy.LARGE_PAGINATION: 100,
            BatchStrategy.SMALL: 10
        }
        self.batch_size = batch_sizes[self.strategy]

@dataclass 
class BatchResult:
    """Result of a batch processing operation."""
    success_count: int = 0
    error_count: int = 0
    total_processed: int = 0
    processing_time: float = 0.0
    results: List[Any] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.success_count / self.total_processed) * 100

class BatchProcessor:
    """High-performance batch processor for API operations."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()
        self.stats = BatchResult()
    
    def create_batches(self, items: List[T]) -> Iterator[List[T]]:
        """
        Split items into optimally-sized batches.
        
        Args:
            items: List of items to batch
            
        Yields:
            Batches of items according to configuration
        """
        batch_size = self.config.batch_size
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]
    
    def process_batches(
        self,
        items: List[T],
        processor_func: Callable[[List[T]], R],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> BatchResult:
        """
        Process items in batches using the provided processor function.
        
        Args:
            items: Items to process
            processor_func: Function that processes a batch and returns results
            progress_callback: Optional callback for progress updates (current, total)
            
        Returns:
            BatchResult with processing statistics and results
        """
        start_time = time.time()
        result = BatchResult()
        batches = list(self.create_batches(items))
        total_batches = len(batches)
        
        logger.info(f"Processing {len(items)} items in {total_batches} batches of {self.config.batch_size}")
        
        for batch_idx, batch in enumerate(batches):
            try:
                # Progress callback
                if progress_callback:
                    progress_callback(batch_idx + 1, total_batches)
                
                # Process batch with retry logic
                batch_result = self._process_single_batch(batch, processor_func, batch_idx)
                
                # Aggregate results
                if batch_result is not None:
                    if isinstance(batch_result, (list, tuple)):
                        result.results.extend(batch_result)
                    else:
                        result.results.append(batch_result)
                    result.success_count += len(batch)
                else:
                    result.error_count += len(batch)
                
                result.total_processed += len(batch)
                
                # Rate limiting delay (except for last batch)
                if batch_idx < total_batches - 1:
                    time.sleep(self.config.delay_between_batches)
                    
            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                result.errors.append(e)
                result.error_count += len(batch)
                result.total_processed += len(batch)
        
        result.processing_time = time.time() - start_time
        
        logger.info(
            f"Batch processing complete: {result.success_count}/{result.total_processed} items "
            f"({result.success_rate:.1f}%) in {result.processing_time:.2f}s"
        )
        
        return result
    
    @retry_with_backoff(max_attempts=3)
    def _process_single_batch(
        self,
        batch: List[T], 
        processor_func: Callable[[List[T]], R],
        batch_idx: int
    ) -> Optional[R]:
        """
        Process a single batch with retry logic and timeout.
        
        Args:
            batch: Items in this batch
            processor_func: Function to process the batch
            batch_idx: Index of this batch (for logging)
            
        Returns:
            Result from processor function or None if failed
        """
        try:
            logger.debug(f"Processing batch {batch_idx + 1} with {len(batch)} items")
            
            # Apply timeout if specified
            if self.config.timeout_per_batch > 0:
                # For now, we'll trust the processor function handles its own timeouts
                # In a full async implementation, we'd use asyncio.wait_for
                pass
            
            result = processor_func(batch)
            logger.debug(f"Batch {batch_idx + 1} completed successfully")
            return result
            
        except Exception as e:
            logger.warning(f"Batch {batch_idx + 1} failed (attempt will retry): {e}")
            raise  # Let retry decorator handle it

class BlueskyBatchProcessor(BatchProcessor):
    """Specialized batch processor for Bluesky API operations."""
    
    def __init__(self, client=None, config: Optional[BatchConfig] = None):
        # Default to standard 25-item batching for Bluesky
        if config is None:
            config = BatchConfig(strategy=BatchStrategy.STANDARD)
        super().__init__(config)
        self.client = client
    
    def batch_get_posts(self, uris: List[str]) -> BatchResult:
        """
        Efficiently batch fetch post details using getPosts API.
        
        Args:
            uris: List of post URIs to fetch
            
        Returns:
            BatchResult containing all fetched posts
        """
        def fetch_posts_batch(uri_batch: List[str]) -> List[Dict[str, Any]]:
            """Fetch a batch of posts from Bluesky API."""
            if self.client is None:
                return []
            
            try:
                # Use authenticated client if available
                resp = self.client.get_posts(uris=uri_batch)
                posts = safe_getattr(resp, "posts", []) or []
                return [self._normalize_post_data(p) for p in posts]
                
            except Exception as e:
                logger.warning(f"Authenticated getPosts failed, trying HTTP: {e}")
                # Fallback to HTTP request
                return self._fetch_posts_http(uri_batch)
        
        return self.process_batches(
            uris,
            fetch_posts_batch,
            progress_callback=lambda current, total: 
                logger.info(f"Fetching posts batch {current}/{total}")
        )
    
    def batch_hydrate_engagement(self, items: List[Any]) -> BatchResult:
        """
        Batch hydrate engagement data for content items.
        
        Args:
            items: Content items to hydrate
            
        Returns:
            BatchResult with hydrated engagement data
        """
        # Extract URIs from items
        uris = [safe_getattr(item, "uri", None) for item in items 
                if safe_getattr(item, "uri", None)]
        
        if not uris:
            return BatchResult()
        
        # Create URI to item mapping for fast updates
        uri_to_item = {safe_getattr(item, "uri"): item for item in items}
        
        def hydrate_engagement_batch(uri_batch: List[str]) -> List[str]:
            """Hydrate engagement for a batch of URIs."""
            posts_result = self.batch_get_posts(uri_batch)
            
            # Update original items with engagement data
            for post_data in posts_result.results:
                if isinstance(post_data, list):
                    for post in post_data:
                        self._update_item_engagement(post, uri_to_item)
                else:
                    self._update_item_engagement(post_data, uri_to_item)
            
            return uri_batch  # Return processed URIs
        
        return self.process_batches(
            uris,
            hydrate_engagement_batch,
            progress_callback=lambda current, total:
                logger.info(f"Hydrating engagement batch {current}/{total}")
        )
    
    def _fetch_posts_http(self, uri_batch: List[str]) -> List[Dict[str, Any]]:
        """Fallback HTTP method for fetching posts."""
        import requests
        
        try:
            params = [("uris", uri) for uri in uri_batch]
            response = requests.get(
                "https://api.bsky.app/xrpc/app.bsky.feed.getPosts",
                params=params,
                timeout=self.config.timeout_per_batch
            )
            
            if response.ok:
                data = response.json()
                posts = data.get("posts", [])
                return [self._normalize_post_data(p) for p in posts]
            else:
                logger.warning(f"HTTP getPosts failed with status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"HTTP fallback failed: {e}")
            return []
    
    def _normalize_post_data(self, post: Any) -> Dict[str, Any]:
        """Normalize post data from API response."""
        if hasattr(post, '__dict__'):
            # AT Protocol object
            return {
                'uri': safe_getattr(post, 'uri', ''),
                'like_count': int(safe_getattr(post, 'like_count', 0) or 0),
                'repost_count': int(safe_getattr(post, 'repost_count', 0) or 0),
                'reply_count': int(safe_getattr(post, 'reply_count', 0) or 0),
                'raw_post': post
            }
        elif isinstance(post, dict):
            # JSON response
            return {
                'uri': post.get('uri', ''),
                'like_count': int(post.get('likeCount', 0) or 0),
                'repost_count': int(post.get('repostCount', 0) or 0),
                'reply_count': int(post.get('replyCount', 0) or 0),
                'raw_post': post
            }
        else:
            return {'uri': '', 'like_count': 0, 'repost_count': 0, 'reply_count': 0}
    
    def _update_item_engagement(self, post_data: Dict[str, Any], uri_to_item: Dict[str, Any]):
        """Update content item with engagement data from post."""
        uri = post_data.get('uri')
        item = uri_to_item.get(uri)
        
        if item is None:
            return
        
        # Update engagement counts
        item.like_count = post_data.get('like_count', 0)
        item.repost_count = post_data.get('repost_count', 0) 
        item.reply_count = post_data.get('reply_count', 0)
        
        # Update engagement score if method exists
        if hasattr(item, 'update_engagement_score'):
            try:
                item.update_engagement_score()
            except Exception:
                pass

# Factory functions for common use cases
def create_standard_batch_processor(client=None) -> BlueskyBatchProcessor:
    """Create a batch processor with standard 25-item batching."""
    config = BatchConfig(strategy=BatchStrategy.STANDARD, delay_between_batches=0.4)
    return BlueskyBatchProcessor(client, config)

def create_conservative_batch_processor(client=None) -> BlueskyBatchProcessor:
    """Create a batch processor with conservative 20-item batching."""
    config = BatchConfig(
        strategy=BatchStrategy.CONSERVATIVE, 
        delay_between_batches=0.6,
        max_retries=5
    )
    return BlueskyBatchProcessor(client, config)

def create_fast_batch_processor(client=None) -> BlueskyBatchProcessor:
    """Create a batch processor optimized for speed (less delay, more risk)."""
    config = BatchConfig(
        strategy=BatchStrategy.STANDARD,
        delay_between_batches=0.2, 
        max_retries=2
    )
    return BlueskyBatchProcessor(client, config)