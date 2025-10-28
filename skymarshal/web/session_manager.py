"""
Unified session management for Skymarshal web interface.

This module provides centralized session state management, replacing scattered
session data storage across multiple dictionaries and Flask session variables.

Key Features:
- Single source of truth for user session state
- Automatic cleanup of expired sessions
- Thread-safe session operations
- Support for multiple storage backends (in-memory, Redis, SQLite)
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from ..auth import AuthManager


@dataclass
class UserSession:
    """Single source of truth for user session state.
    
    This replaces the scattered state management across:
    - Flask session dict
    - progress_data global dict
    - auth_storage global dict
    - Multiple fallback lookups in get_json_path()
    """
    
    session_id: str
    handle: str
    auth_manager: AuthManager
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    
    # Data paths
    json_path: Optional[Path] = None
    car_path: Optional[Path] = None
    
    # Content metadata
    total_items: int = 0
    content_types: Dict[str, int] = field(default_factory=dict)
    
    # Processing state
    is_processing: bool = False
    last_operation: Optional[str] = None
    
    # Security flags
    used_regular_password: bool = False
    
    def touch(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = time.time()
    
    def is_expired(self, ttl_seconds: int = 86400) -> bool:
        """Check if session has expired (default: 24 hours)."""
        return (time.time() - self.last_accessed) > ttl_seconds
    
    def to_dict(self) -> dict:
        """Serialize to dict for Flask session storage."""
        return {
            'session_id': self.session_id,
            'handle': self.handle,
            'json_path': str(self.json_path) if self.json_path else None,
            'car_path': str(self.car_path) if self.car_path else None,
            'total_items': self.total_items,
            'content_types': self.content_types,
            'used_regular_password': self.used_regular_password,
        }


class SessionManager:
    """Centralized session management with automatic cleanup.
    
    Usage:
        session_mgr = SessionManager()
        
        # Create new session
        session = session_mgr.create_session(handle, auth_manager)
        
        # Get existing session
        session = session_mgr.get_session(session_id)
        
        # Update session
        session.json_path = Path("/path/to/data.json")
        session_mgr.save_session(session)
        
        # Cleanup
        session_mgr.clear_session(session_id)
    """
    
    def __init__(self, session_ttl: int = 86400):
        """Initialize session manager.
        
        Args:
            session_ttl: Session time-to-live in seconds (default: 24 hours)
        """
        self._sessions: Dict[str, UserSession] = {}
        self._lock = Lock()
        self._session_ttl = session_ttl
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # Cleanup every hour
    
    def create_session(
        self,
        handle: str,
        auth_manager: AuthManager,
        used_regular_password: bool = False
    ) -> UserSession:
        """Create a new user session.
        
        Args:
            handle: User's Bluesky handle
            auth_manager: Authenticated AuthManager instance
            used_regular_password: Whether user used regular password vs app password
            
        Returns:
            New UserSession instance
        """
        session_id = secrets.token_hex(16)
        session = UserSession(
            session_id=session_id,
            handle=handle,
            auth_manager=auth_manager,
            used_regular_password=used_regular_password,
        )
        
        with self._lock:
            self._sessions[session_id] = session
            self._maybe_cleanup()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            UserSession if found and not expired, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            
            if session is None:
                return None
            
            if session.is_expired(self._session_ttl):
                del self._sessions[session_id]
                return None
            
            session.touch()
            return session
    
    def save_session(self, session: UserSession) -> None:
        """Update an existing session.
        
        Args:
            session: UserSession to save
        """
        with self._lock:
            session.touch()
            self._sessions[session.session_id] = session
    
    def clear_session(self, session_id: str) -> None:
        """Remove a session.
        
        Args:
            session_id: Session identifier to remove
        """
        with self._lock:
            self._sessions.pop(session_id, None)
    
    def get_session_by_handle(self, handle: str) -> Optional[UserSession]:
        """Find active session for a handle.
        
        Args:
            handle: User's Bluesky handle
            
        Returns:
            Most recently accessed UserSession for handle, or None
        """
        with self._lock:
            sessions = [
                s for s in self._sessions.values()
                if s.handle == handle and not s.is_expired(self._session_ttl)
            ]
            
            if not sessions:
                return None
            
            # Return most recently accessed
            return max(sessions, key=lambda s: s.last_accessed)
    
    def _maybe_cleanup(self) -> None:
        """Cleanup expired sessions periodically (called with lock held)."""
        now = time.time()
        
        if (now - self._last_cleanup) < self._cleanup_interval:
            return
        
        # Find expired sessions
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(self._session_ttl)
        ]
        
        # Remove them
        for sid in expired:
            del self._sessions[sid]
        
        self._last_cleanup = now
        
        if expired:
            print(f"SessionManager: Cleaned up {len(expired)} expired sessions")
    
    def cleanup_all_expired(self) -> int:
        """Force cleanup of all expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            expired = [
                sid for sid, session in self._sessions.items()
                if session.is_expired(self._session_ttl)
            ]
            
            for sid in expired:
                del self._sessions[sid]
            
            self._last_cleanup = time.time()
            return len(expired)
    
    def get_stats(self) -> dict:
        """Get session manager statistics.
        
        Returns:
            Dict with session counts and other metrics
        """
        with self._lock:
            active = len([
                s for s in self._sessions.values()
                if not s.is_expired(self._session_ttl)
            ])
            
            return {
                'total_sessions': len(self._sessions),
                'active_sessions': active,
                'expired_sessions': len(self._sessions) - active,
                'unique_handles': len(set(s.handle for s in self._sessions.values())),
            }
