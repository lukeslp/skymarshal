"""Filesystem cache for network data with TTL support.

Simplified from blueballs cache_service.py — filesystem only, no Redis.
Stores JSON data with metadata (timestamp) for TTL-based expiration.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = "~/.skymarshal/network_cache"

# Default TTL: 1 hour
DEFAULT_TTL_SECONDS = 3600


class NetworkCache:
    """Filesystem-based cache for network fetch results.

    Cache keys are derived from handle + fetch parameters.
    Each cache entry stores JSON data alongside a metadata sidecar
    with the creation timestamp for TTL checks.
    """

    def __init__(
        self,
        cache_dir: str = DEFAULT_CACHE_DIR,
        default_ttl: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._base_path = Path(cache_dir).expanduser()
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        logger.info("Network cache initialized at %s", self._base_path)

    def _data_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self._base_path / f"{safe_key}.json"

    def _meta_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self._base_path / f"{safe_key}.meta.json"

    def make_key(
        self,
        handle: str,
        *,
        include_followers: bool = True,
        include_following: bool = True,
        max_followers: Optional[int] = None,
        max_following: Optional[int] = None,
        mode: str = "balanced",
    ) -> str:
        """Build a cache key from fetch parameters."""
        parts = [
            f"network:{handle}",
            "follower" if include_followers else "nofollower",
            "following" if include_following else "nofollowing",
            f"maxf{max_followers or 500}",
            f"maxt{max_following or 500}",
            mode,
        ]
        return ":".join(parts)

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Return cached data if present and not expired."""
        data_path = self._data_path(key)
        meta_path = self._meta_path(key)

        if not data_path.exists():
            return None

        # Check TTL via metadata
        effective_ttl = ttl if ttl is not None else self._default_ttl
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                created_at = meta.get("created_at", 0)
                if time.time() - created_at > effective_ttl:
                    logger.info("Cache expired for key '%s'", key)
                    self.delete(key)
                    return None
            except (json.JSONDecodeError, OSError):
                pass

        # Read data
        try:
            content = data_path.read_bytes()
            if not content:
                data_path.unlink(missing_ok=True)
                return None
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cache read error for '%s': %s", key, exc)
            self.delete(key)
            return None

    def set(self, key: str, value: Any) -> None:
        """Store data in cache."""
        data_path = self._data_path(key)
        meta_path = self._meta_path(key)

        try:
            data_path.write_text(json.dumps(value, separators=(",", ":")))
            meta_path.write_text(
                json.dumps({"created_at": time.time(), "key": key})
            )
            logger.info("Cached data for key '%s'", key)
        except OSError as exc:
            logger.warning("Cache write error for '%s': %s", key, exc)

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        for path in (self._data_path(key), self._meta_path(key)):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def clear(self) -> int:
        """Remove all cached entries. Returns count of files removed."""
        count = 0
        for path in self._base_path.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError:
                pass
        logger.info("Cleared %d cache files", count)
        return count
