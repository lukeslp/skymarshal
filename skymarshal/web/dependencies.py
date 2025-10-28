"""
Dependency injection for Skymarshal web interface.

This module provides Flask request-scoped dependency management,
replacing the pattern of recreating managers in every route.

Key Features:
- Request-scoped service instances
- Automatic manager initialization
- Consistent settings and auth management
- Reduces code duplication across routes
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import g, session, current_app

from ..auth import AuthManager
from ..data_manager import DataManager
from ..deletion import DeletionManager
from ..models import UserSettings
from ..search import SearchManager
from ..services import ContentService
from ..settings import SettingsManager
from .session_manager import SessionManager, UserSession


def get_session_manager() -> SessionManager:
    """Get or create the application-wide session manager.
    
    Returns:
        SessionManager instance
    """
    if 'session_manager' not in g:
        g.session_manager = current_app.config.get('SESSION_MANAGER')
        if g.session_manager is None:
            # Fallback: create a new one if not configured
            g.session_manager = SessionManager()
    return g.session_manager


def get_user_session() -> Optional[UserSession]:
    """Get the current user's session.
    
    Returns:
        UserSession if authenticated, None otherwise
    """
    if 'user_session' not in g:
        session_id = session.get('session_id')
        if session_id:
            session_mgr = get_session_manager()
            g.user_session = session_mgr.get_session(session_id)
        else:
            g.user_session = None
    return g.user_session


def get_auth_manager() -> Optional[AuthManager]:
    """Get the current user's auth manager.
    
    Returns:
        AuthManager if authenticated, None otherwise
    """
    user_session = get_user_session()
    return user_session.auth_manager if user_session else None


def get_settings() -> UserSettings:
    """Get user settings (request-scoped).
    
    Returns:
        UserSettings instance
    """
    if 'settings' not in g:
        settings_file = Path.home() / ".car_inspector_settings.json"
        settings_manager = SettingsManager(settings_file)
        g.settings = settings_manager.settings
    return g.settings


def get_storage_paths() -> tuple[Path, Path, Path]:
    """Get standard storage paths.
    
    Returns:
        Tuple of (skymarshal_dir, backups_dir, json_dir)
    """
    if 'storage_paths' not in g:
        skymarshal_dir = Path.home() / '.skymarshal'
        backups_dir = skymarshal_dir / 'cars'
        json_dir = skymarshal_dir / 'json'
        
        # Ensure directories exist
        skymarshal_dir.mkdir(exist_ok=True)
        backups_dir.mkdir(exist_ok=True)
        json_dir.mkdir(exist_ok=True)
        
        g.storage_paths = (skymarshal_dir, backups_dir, json_dir)
    
    return g.storage_paths


def get_data_manager() -> Optional[DataManager]:
    """Get data manager for current user (request-scoped).
    
    Returns:
        DataManager if authenticated, None otherwise
    """
    if 'data_manager' not in g:
        auth_manager = get_auth_manager()
        if not auth_manager:
            return None
        
        settings = get_settings()
        skymarshal_dir, backups_dir, json_dir = get_storage_paths()
        
        g.data_manager = DataManager(
            auth_manager,
            settings,
            skymarshal_dir,
            backups_dir,
            json_dir
        )
    
    return g.data_manager


def get_search_manager() -> Optional[SearchManager]:
    """Get search manager for current user (request-scoped).
    
    Returns:
        SearchManager if authenticated, None otherwise
    """
    if 'search_manager' not in g:
        auth_manager = get_auth_manager()
        if not auth_manager:
            return None
        
        settings = get_settings()
        g.search_manager = SearchManager(auth_manager, settings)
    
    return g.search_manager


def get_deletion_manager() -> Optional[DeletionManager]:
    """Get deletion manager for current user (request-scoped).
    
    Returns:
        DeletionManager if authenticated, None otherwise
    """
    if 'deletion_manager' not in g:
        auth_manager = get_auth_manager()
        if not auth_manager:
            return None
        
        settings = get_settings()
        g.deletion_manager = DeletionManager(auth_manager, settings)
    
    return g.deletion_manager


def get_content_service() -> Optional[ContentService]:
    """Get content service for current user (request-scoped).
    
    Returns:
        ContentService if authenticated, None otherwise
    """
    if 'content_service' not in g:
        auth_manager = get_auth_manager()
        if not auth_manager:
            return None
        
        settings_path = Path.home() / ".car_inspector_settings.json"
        storage_root = Path.home() / ".skymarshal"
        
        g.content_service = ContentService(
            settings_path=settings_path,
            storage_root=storage_root,
            auth_manager=auth_manager
        )
    
    return g.content_service


def get_json_path() -> Optional[Path]:
    """Get the current user's JSON data path with intelligent fallback.
    
    This replaces the complex fallback logic scattered across multiple functions.
    
    Returns:
        Path to user's JSON data file, or None if not found
    """
    user_session = get_user_session()
    if not user_session:
        return None
    
    # Check session first
    if user_session.json_path and user_session.json_path.exists():
        return user_session.json_path
    
    # Fall back to finding recent exports
    _, _, json_dir = get_storage_paths()
    handle = user_session.handle
    
    # Try exact match
    safe_handle = handle.replace('.', '_')
    primary = json_dir / f"{safe_handle}.json"
    if primary.exists():
        # Update session
        user_session.json_path = primary
        get_session_manager().save_session(user_session)
        return primary
    
    # Try timestamped files
    candidates = sorted(
        json_dir.glob(f"{safe_handle}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if candidates:
        # Update session with most recent
        user_session.json_path = candidates[0]
        get_session_manager().save_session(user_session)
        return candidates[0]
    
    return None
