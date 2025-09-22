#!/usr/bin/env python3
"""
Shared utilities for Skymarshal site_gpt5 web interfaces.

Common functions extracted from app.py, web_simple.py, and hydrate_last_500.py
to reduce code duplication and improve maintainability.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Callable, TypeVar
from functools import wraps
from dataclasses import dataclass

try:
    from atproto import Client
except ImportError:
    Client = None  # type: ignore

T = TypeVar('T')

@dataclass
class HydrationConfig:
    """Configuration for engagement hydration operations."""
    fast_hydrate: bool = False
    budget_seconds: float = 10.0
    batch_size: int = 25  # Standardized for optimal Bluesky API efficiency
    max_retries: int = 3
    rate_limit_delay: float = 0.4
    api_timeout: float = 3.0
    small_dataset_threshold: int = 50
    
    @property
    def use_batch_processing(self) -> bool:
        """Whether to use the new batch processing system."""
        return True


def normalize_handle(handle: str) -> str:
    """
    Normalize Bluesky handle to canonical format.
    
    Args:
        handle: Raw handle input (may include @, may be incomplete)
        
    Returns:
        Normalized handle in format: username.bsky.social
    """
    h = handle.lstrip("@").strip()
    if "." not in h:
        h = f"{h}.bsky.social"
    return h


def create_bluesky_client(authenticated: bool = False) -> Optional[Client]:
    """
    Create Bluesky AT Protocol client with consistent error handling.
    
    Args:
        authenticated: Whether to create authenticated client (requires login)
        
    Returns:
        Client instance or None if creation fails
    """
    if Client is None:
        return None
    
    try:
        return Client()
    except Exception:
        return None


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = base_delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(min(delay, max_delay))
                        delay *= 2
                    
            # Re-raise the last exception if all attempts failed
            if last_exception:
                raise last_exception
            
            # This should never be reached, but for type safety
            raise RuntimeError("Unexpected retry logic failure")
        
        return wrapper
    return decorator


class PostDataExporter:
    """Utility class for consistent post data export formatting."""
    
    @staticmethod
    def export_post_data(
        items: List[Any],
        handle: str,
        did: Optional[str] = None,
        display_name: Optional[str] = None,
        quotes_by_uri: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Export post items to standardized JSON format.
        
        Args:
            items: List of content items (posts, likes, reposts)
            handle: User handle
            did: User DID identifier
            display_name: User display name
            quotes_by_uri: Mapping of post URIs to quote counts
            
        Returns:
            Dictionary with standardized export format
        """
        from datetime import datetime
        
        export_data = []
        quotes_by_uri = quotes_by_uri or {}
        
        for item in items:
            item_dict = {
                'uri': getattr(item, 'uri', ''),
                'cid': getattr(item, 'cid', ''),
                'content_type': getattr(item, 'content_type', ''),
                'text': getattr(item, 'text', ''),
                'created_at': getattr(item, 'created_at', ''),
                'like_count': getattr(item, 'like_count', 0),
                'repost_count': getattr(item, 'repost_count', 0),
                'reply_count': getattr(item, 'reply_count', 0),
                'quote_count': quotes_by_uri.get(getattr(item, 'uri', ''), 0),
                'engagement_score': getattr(item, 'engagement_score', 0),
                'raw_data': getattr(item, 'raw_data', {})
            }
            export_data.append(item_dict)
        
        return {
            'handle': handle,
            'did': did,
            'display_name': display_name,
            'exported_at': datetime.now().isoformat(),
            'count': len(export_data),
            'posts': export_data
        }


class EngagementAggregator:
    """Utility class for calculating engagement statistics."""
    
    @staticmethod
    def calculate_totals(items: List[Any]) -> Dict[str, Any]:
        """
        Calculate total engagement metrics for a list of items.
        
        Args:
            items: List of content items with engagement data
            
        Returns:
            Dictionary with aggregated engagement totals
        """
        if not items:
            return {
                'posts': 0,
                'likes_received': 0,
                'reposts_received': 0,
                'replies_received': 0,
                'quotes_received': 0,
                'total_engagement': 0,
                'avg_engagement': 0.0
            }
        
        total_likes = sum(int(getattr(item, 'like_count', 0) or 0) for item in items)
        total_reposts = sum(int(getattr(item, 'repost_count', 0) or 0) for item in items)
        total_replies = sum(int(getattr(item, 'reply_count', 0) or 0) for item in items)
        total_quotes = sum(int(getattr(item, 'quote_count', 0) or 0) for item in items)
        
        # Calculate engagement scores
        total_engagement = 0
        for item in items:
            likes = int(getattr(item, 'like_count', 0) or 0)
            reposts = int(getattr(item, 'repost_count', 0) or 0)
            replies = int(getattr(item, 'reply_count', 0) or 0)
            
            # Use item's engagement score if available, otherwise calculate
            if hasattr(item, 'engagement_score') and item.engagement_score:
                total_engagement += int(item.engagement_score)
            else:
                # Default engagement formula: likes + (2 × reposts) + (2.5 × replies)
                total_engagement += likes + (2 * reposts) + (2.5 * replies)
        
        avg_engagement = total_engagement / len(items) if items else 0.0
        
        return {
            'posts': len(items),
            'likes_received': total_likes,
            'reposts_received': total_reposts,
            'replies_received': total_replies,
            'quotes_received': total_quotes,
            'total_engagement': int(total_engagement),
            'avg_engagement': round(avg_engagement, 2)
        }


class APIPageManager:
    """Generic pagination handler for Bluesky API endpoints."""
    
    def __init__(self, config: HydrationConfig):
        self.config = config
    
    def paginate(
        self,
        request_func: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
        base_params: Dict[str, Any],
        items_key: str,
        max_pages: int = 50
    ) -> int:
        """
        Generic pagination for API endpoints that return paginated results.
        
        Args:
            request_func: Function that makes the API request
            base_params: Base parameters for the request
            items_key: Key in response containing the items array
            max_pages: Maximum number of pages to fetch
            
        Returns:
            Total count of items across all pages
        """
        total = 0
        cursor: Optional[str] = None
        pages = 0
        
        while pages < max_pages:
            params = dict(base_params)
            params["limit"] = 100
            if cursor:
                params["cursor"] = cursor
                
            data = request_func(params)
            if not data or items_key not in data:
                break
                
            items = data.get(items_key, []) or []
            total += len(items)
            cursor = data.get("cursor")
            
            if not cursor:
                break
                
            pages += 1
            time.sleep(self.config.rate_limit_delay)
        
        return total


def safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """
    Safely get attribute from object with fallback.
    
    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute not found
        
    Returns:
        Attribute value or default
    """
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def format_file_safe_name(handle: str, timestamp: Optional[str] = None) -> str:
    """
    Create file-safe name from handle and optional timestamp.
    
    Args:
        handle: User handle
        timestamp: Optional timestamp string
        
    Returns:
        File-safe name suitable for use in filenames
    """
    from datetime import datetime
    
    safe_handle = handle.replace('.', '_').replace('@', '')
    
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{safe_handle}_{timestamp}"