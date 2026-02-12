"""Sync HTTP client for the Bluesky public API with rate limiting.

Ported from blueballs/backend/app/services/bluesky_client.py.
Uses sync requests (eventlet-compatible) instead of async httpx.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

# Bluesky public API base URL
BLUESKY_API_BASE = "https://public.api.bsky.app/xrpc"

# Defaults
DEFAULT_MAX_POINTS = 3000
DEFAULT_WINDOW_SECONDS = 3600
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3


class RateLimiter:
    """Points-based rate limiter for Bluesky API.

    Bluesky uses 3000 points/hour for unauthenticated, 5000 for authenticated.
    Thread-safe via threading.Lock (eventlet-compatible).
    """

    def __init__(
        self,
        max_points: int = DEFAULT_MAX_POINTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.max_points = max_points
        self.window_seconds = window_seconds
        self._requests: List[tuple] = []  # (timestamp, points_cost)
        self._lock = threading.Lock()

    def acquire(self, points_cost: int = 1) -> None:
        """Block until we can safely make a request without exceeding rate limit."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self._requests = [
                (ts, cost) for ts, cost in self._requests if ts > cutoff
            ]
            current_points = sum(cost for _, cost in self._requests)

            if current_points + points_cost > self.max_points:
                if self._requests:
                    oldest_ts = self._requests[0][0]
                    wait_time = (oldest_ts + self.window_seconds) - now + 1
                    if wait_time > 0:
                        logger.warning(
                            "Rate limit approaching (%d/%d points). Waiting %.1fs...",
                            current_points,
                            self.max_points,
                            wait_time,
                        )
                        # Release lock during sleep so other threads aren't blocked
                        self._lock.release()
                        try:
                            time.sleep(wait_time)
                        finally:
                            self._lock.acquire()
                        # Retry after waiting
                        return self.acquire(points_cost)

            self._requests.append((now, points_cost))

    def get_usage_stats(self) -> Dict[str, int]:
        """Return current rate limit usage statistics."""
        now = time.time()
        cutoff = now - self.window_seconds
        recent = [(ts, cost) for ts, cost in self._requests if ts > cutoff]
        total_points = sum(cost for _, cost in recent)
        return {
            "points_used": total_points,
            "points_remaining": max(0, self.max_points - total_points),
            "max_points": self.max_points,
            "requests_in_window": len(recent),
        }


class BlueskyClient:
    """Sync wrapper around the Bluesky public XRPC API.

    Uses requests.Session with rate limiting and exponential backoff.
    """

    def __init__(
        self,
        *,
        base_url: str = BLUESKY_API_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        max_points: int = DEFAULT_MAX_POINTS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._rate_limiter = RateLimiter(max_points=max_points)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "SkymarshalNetworkExplorer/1.0 (+https://dr.eamer.dev)",
                "Accept": "application/json",
            }
        )

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()

    def get_rate_limit_stats(self) -> Dict[str, int]:
        return self._rate_limiter.get_usage_stats()

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        points_cost: int = 1,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Dict[str, Any]:
        """Make a request with rate limiting and exponential backoff."""
        self._rate_limiter.acquire(points_cost)

        last_exception: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                url = f"{self._base_url}{endpoint}"
                response = self._session.get(url, params=params, timeout=self._timeout)
                response.raise_for_status()
                return response.json()

            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0

                # 429 Rate Limit
                if status == 429:
                    wait_time = (2**attempt) * 1.0
                    logger.warning(
                        "Rate limit (429) on %s (attempt %d/%d). Waiting %.1fs...",
                        endpoint,
                        attempt + 1,
                        max_retries,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    last_exception = exc
                    continue

                # 5xx Server Error
                if 500 <= status < 600:
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) * 0.5
                        logger.warning(
                            "Server error %d on %s (attempt %d/%d). Retrying in %.1fs...",
                            status,
                            endpoint,
                            attempt + 1,
                            max_retries,
                            wait_time,
                        )
                        time.sleep(wait_time)
                        last_exception = exc
                        continue
                    raise

                # 4xx Client Error (except 429)
                raise

            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) * 0.5
                    logger.warning(
                        "Network error on %s (attempt %d/%d): %s. Retrying in %.1fs...",
                        endpoint,
                        attempt + 1,
                        max_retries,
                        exc,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    last_exception = exc
                    continue
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request to {endpoint} failed after {max_retries} retries")

    # -----------------------------------------------------------------------
    # Profile endpoints
    # -----------------------------------------------------------------------

    def get_profile(self, handle: str) -> Optional[Dict[str, Any]]:
        """Return profile info for a handle."""
        try:
            return self._request(
                "/app.bsky.actor.getProfile", params={"actor": handle}
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logger.warning("Profile not found for '%s'", handle)
                return None
            raise

    def get_profiles_batch(self, handles: Iterable[str]) -> List[Dict[str, Any]]:
        """Return profile info for up to 25 handles."""
        handle_list = list(handles)[:25]
        if not handle_list:
            return []
        try:
            data = self._request(
                "/app.bsky.actor.getProfiles", params={"actors": handle_list}
            )
        except requests.HTTPError:
            logger.error("Batch profile lookup failed for %d handles", len(handle_list))
            raise
        return data.get("profiles", [])

    # -----------------------------------------------------------------------
    # Graph endpoints
    # -----------------------------------------------------------------------

    def get_follows(
        self, handle: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return profiles followed by the handle."""
        return self._paginate_collection(
            "/app.bsky.graph.getFollows", handle, limit, key="follows"
        )

    def get_followers(
        self, handle: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return profiles following the handle."""
        return self._paginate_collection(
            "/app.bsky.graph.getFollowers", handle, limit, key="followers"
        )

    def _paginate_collection(
        self,
        endpoint: str,
        handle: str,
        limit: Optional[int],
        *,
        key: str,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            params: Dict[str, Any] = {"actor": handle, "limit": 100}
            if cursor:
                params["cursor"] = cursor

            response = self._request(endpoint, params=params)
            batch = response.get(key, [])
            items.extend(batch)

            if limit is not None and len(items) >= limit:
                return items[:limit]

            cursor = response.get("cursor")
            if not cursor or not batch:
                break

        return items
