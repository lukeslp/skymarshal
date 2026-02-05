
import sqlite3
import json
import secrets
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

class SharedPostManager:
    """Manages storage and retrieval of shared posts using SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shared_posts (
                    id TEXT PRIMARY KEY,
                    uri TEXT NOT NULL,
                    content JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_share(self, post_data: Dict[str, Any]) -> str:
        """
        Save a post to the shared database and return its share ID.
        
        Args:
            post_data: Dictionary containing post content (text, author, images, etc.)
            
        Returns:
            str: The unique share ID (8 character hex)
        """
        share_id = secrets.token_hex(4)  # 8 characters
        
        # Ensure 'uri' exists in post_data, fallback to generating one if missing (shouldn't happen for real posts)
        uri = post_data.get('uri', f"unknown:{share_id}")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO shared_posts (id, uri, content) VALUES (?, ?, ?)",
                (share_id, uri, json.dumps(post_data))
            )
            conn.commit()
            
        return share_id

    def get_share(self, share_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a shared post by its ID.
        
        Args:
            share_id: The 8-character share ID
            
        Returns:
            Optional[Dict]: The post data dict if found, else None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT content, created_at FROM shared_posts WHERE id = ?",
                (share_id,)
            )
            row = cursor.fetchone()
            
            if row:
                data = json.loads(row['content'])
                data['shared_at'] = row['created_at']
                return data
                
        return None
