"""
Skymarshal Data Management Operations

File Purpose: Handle data export, import, file operations, and content processing
Primary Functions/Classes: DataManager
Inputs and Outputs (I/O): Data files, backup files, Bluesky data, filesystem operations

This module manages all data-related operations including downloading from Bluesky,
importing/exporting backup files, data processing, and refreshing engagement info.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from atproto import Client
from atproto_core.car import CAR

try:
    # Try new libipld-based approach first (atproto >= 0.0.26)
    from libipld import decode_dag_cbor

    cbor_decode = decode_dag_cbor
except ImportError:
    try:
        # Fallback to older atproto_core.cbor approach
        from atproto_core import cbor as at_cbor

        cbor_decode = at_cbor.loads
    except (ImportError, AttributeError):
        try:
            # Last resort: standard cbor2 library
            import cbor2

            cbor_decode = cbor2.loads
        except ImportError:
            cbor_decode = None
from contextlib import contextmanager

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from .auth import AuthManager
from .exceptions import (
    APIError,
    DataError,
    FileError,
    AuthenticationError,
    handle_error,
    safe_execute,
)
from .models import (
    ContentItem,
    UserSettings,
    calculate_engagement_score,
    console,
    merge_content_items,
    parse_datetime,
)


class DataManager:
    """Manages data operations and file handling."""

    def __init__(
        self,
        auth_manager: AuthManager,
        settings: UserSettings,
        skymarshal_dir: Path,
        backups_dir: Path,
        json_dir: Path,
    ):
        self.auth = auth_manager
        self.settings = settings
        self.skymarshal_dir = skymarshal_dir
        self.backups_dir = backups_dir
        self.json_dir = json_dir

    def _resolve_handle_to_did(self, handle: str) -> Optional[str]:
        """Resolve a handle to a DID, with fallback methods."""
        try:
            profile = self.auth.client.get_profile(handle)
            return profile.did
        except Exception as e:
            try:
                result = self.auth.client.resolve_handle(handle)
                return result.did
            except Exception as resolve_error:
                handle_error(
                    console,
                    APIError(
                        "Handle resolution failed", str(resolve_error), resolve_error
                    ),
                    "Handle resolution",
                )
                return None

    @contextmanager
    def _progress_context(self, description: str = "Processing"):
        """Create a standardized progress context manager."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            yield progress

    def export_user_data(
        self,
        handle: str,
        limit: int = 500,
        categories: Optional[set] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        replace_existing: bool = False,
    ) -> Optional[Path]:
        """Export user data with pagination and light concurrency."""
        try:
            did = self._resolve_handle_to_did(handle)
            if not did:
                return None

            cats = categories or {"posts", "likes", "reposts"}
            results = {}

            console.print()
            with self._progress_context() as progress:
                tasks = {}
                for cat in cats:
                    tasks[cat] = progress.add_task(f"Fetching {cat} (0)", total=limit)

                def make_cb(cat):
                    def _cb(count):
                        progress.update(
                            tasks[cat],
                            completed=min(count, limit),
                            description=f"Fetching {cat} ({count})",
                        )

                    return _cb

                with ThreadPoolExecutor(
                    max_workers=(min(self.settings.category_workers, len(cats)) or 1)
                ) as pool:
                    futs = {}
                    if "posts" in cats:
                        futs["posts"] = pool.submit(
                            self._fetch_posts_records, did, limit, make_cb("posts")
                        )
                    if "likes" in cats:
                        futs["likes"] = pool.submit(
                            self._fetch_likes_records, did, limit, make_cb("likes")
                        )
                    if "reposts" in cats:
                        futs["reposts"] = pool.submit(
                            self._fetch_reposts_records, did, limit, make_cb("reposts")
                        )

                    for k, f in futs.items():
                        results[k] = f.result()

            posts = results.get("posts", [])
            likes = results.get("likes", [])
            reposts = results.get("reposts", [])

            if date_start or date_end:
                posts, likes, reposts = self._apply_date_filter(
                    posts, likes, reposts, date_start, date_end
                )

            if posts:
                console.print()
                console.print("[bold cyan]Step 3:[/] Fetching engagement data for posts...")
                self._hydrate_post_engagement(posts)
                console.print("[green]✓[/] Post engagement data updated")

            if reposts and self.settings.use_subject_engagement_for_reposts:
                console.print()
                console.print("[bold cyan]Step 4:[/] Fetching engagement data for reposts...")
                self._hydrate_repost_subject_engagement(reposts)
                console.print("[green]✓[/] Repost engagement data updated")

            if self.settings.fetch_order == "oldest":
                self._sort_by_date(posts, likes, reposts)

            console.print()
            console.print("[bold cyan]Final Step:[/] Saving data to file...")
            
            export_data = self._build_export_data(
                handle, did, posts, likes, reposts, cats
            )
            export_path = self.json_dir / f"{handle.replace('.', '_')}.json"

            if export_path.exists() and not replace_existing:
                export_data = self._merge_with_existing(export_path, export_data)

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2)
            
            total_items = len(posts) + len(likes) + len(reposts)
            console.print(f"[green]✓[/] Saved {total_items} items to [cyan]{export_path.name}[/]")

            return export_path

        except Exception as e:
            handle_error(
                console, DataError("Data export failed", str(e), e), "Export operation"
            )
            return None

    def download_backup(self, handle: str) -> Optional[Path]:
        """Download backup file for a handle and save under ~/.skymarshal/backups."""
        if not self.auth.client:
            self.auth.client = Client()

        did = self._resolve_handle_to_did(handle)
        if not did:
            return None

        with console.status("Fetching backup file..."):
            try:
                resp = self.auth.call_with_reauth(
                    lambda: self.auth.client.com.atproto.sync.get_repo({"did": did})
                )
                data = (
                    getattr(resp, "body", None) or getattr(resp, "bytes", None) or resp
                )

                if data is None:
                    console.print("Empty response for backup")
                    return None

                out_path = self.backups_dir / f"{handle.replace('.', '_')}.car"
                with open(out_path, "wb") as f:
                    if hasattr(data, "read"):
                        f.write(data.read())
                    else:
                        f.write(data)

                console.print(f"Saved backup to {out_path}")
                return out_path

            except Exception as e:
                console.print(f"Backup download failed: {e}")
                return None

    def create_timestamped_backup(self, handle: str) -> Optional[Path]:
        """Download backup file and save with a timestamped filename."""
        if not self.auth.client:
            self.auth.client = Client()

        did = self._resolve_handle_to_did(handle)
        if not did:
            return None

        with console.status("Fetching backup file..."):
            try:
                resp = self.auth.call_with_reauth(
                    lambda: self.auth.client.com.atproto.sync.get_repo({"did": did})
                )
                data = (
                    getattr(resp, "body", None) or getattr(resp, "bytes", None) or resp
                )

                if data is None:
                    console.print("Empty response for backup")
                    return None

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = self.backups_dir / f"{handle.replace('.', '_')}_{ts}.car"

                with open(out_path, "wb") as f:
                    if hasattr(data, "read"):
                        f.write(data.read())
                    else:
                        f.write(data)

                console.print(f"Backup saved to {out_path}")
                return out_path

            except Exception as e:
                console.print(f"Backup failed: {e}")
                return None
    
    def download_car(self, handle: str) -> Optional[Path]:
        """Download CAR backup file - alias for create_timestamped_backup for compatibility."""
        return self.create_timestamped_backup(handle)
    
    def import_car_replace(self, car_path: Path, handle: str, categories: Optional[set] = None) -> Optional[Path]:
        """Import CAR file replacing existing data - alias for import_backup_replace for compatibility."""
        return self.import_backup_replace(car_path, handle, categories)

    def create_timestamped_backup_with_progress(self, handle: str, progress_callback=None) -> Optional[Path]:
        """Download backup file with progress tracking."""
        if not self.auth.client:
            self.auth.client = Client()

        did = self._resolve_handle_to_did(handle)
        if not did:
            return None

        try:
            # Make the API request
            resp = self.auth.call_with_reauth(
                lambda: self.auth.client.com.atproto.sync.get_repo({"did": did})
            )
            
            # Get response data
            data = getattr(resp, "body", None) or getattr(resp, "bytes", None) or resp
            if data is None:
                console.print("Empty response for backup")
                return None

            # Try to get content length for progress tracking
            total_size = None
            if hasattr(data, '__len__'):
                total_size = len(data)
            elif hasattr(resp, 'headers') and 'content-length' in resp.headers:
                total_size = int(resp.headers['content-length'])

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = self.backups_dir / f"{handle.replace('.', '_')}_{ts}.car"

            downloaded = 0
            chunk_size = 8192  # 8KB chunks

            with open(out_path, "wb") as f:
                if hasattr(data, "read"):
                    # Stream the data in chunks
                    while True:
                        chunk = data.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            try:
                                progress_callback(downloaded, total_size)
                            except:
                                pass  # Continue even if callback fails
                else:
                    # Write all at once if not streamable
                    if isinstance(data, (bytes, bytearray)):
                        f.write(data)
                        downloaded = len(data)
                        if progress_callback:
                            try:
                                progress_callback(downloaded, total_size)
                            except:
                                pass
                    else:
                        f.write(data)

            console.print(f"Backup saved to {out_path}")
            return out_path

        except Exception as e:
            console.print(f"Backup failed: {e}")
            return None

    def import_backup_merge(
        self,
        backup_path: Path,
        handle: Optional[str] = None,
        categories: Optional[set] = None,
    ) -> Optional[Path]:
        """Import records from a backup file, merge/dedupe into the handle's data export."""
        try:
            data = Path(backup_path).read_bytes()
            car = CAR.from_bytes(data)
        except Exception as e:
            console.print(f"Failed to read backup: {e}")
            return None

        decoded = self._decode_car_blocks(car)
        cid_to_path, did = self._extract_backup_metadata(decoded)

        if not did:
            # Try to get DID from auth or prompt user
            did = self.auth.current_did
            if not did and handle:
                # Try to resolve DID from handle
                try:
                    if self.auth.client:
                        profile = self.auth.client.get_profile(handle)
                        did = profile.did
                except Exception:
                    pass

            if not did:
                # For backup files without commit records, we might not have a DID
                # We'll use a placeholder and let the user know
                console.print("No DID found in backup file - using placeholder")
                did = "did:plc:unknown"

        if not handle:
            try:
                prof = self.auth.client.get_profile(did)
                handle = getattr(prof, "handle", None)
            except Exception:
                handle = did.replace(":", "_")

        safe_name = (handle or "unknown").replace(".", "_")
        posts, likes, reposts = self._process_backup_records(
            decoded, cid_to_path, did, handle
        )

        # If authenticated, hydrate post engagement now so JSON persists counts
        try:
            if self.auth.is_authenticated() and posts:
                temp_items = [
                    ContentItem(
                        uri=p.get("uri"),
                        cid=p.get("cid"),
                        content_type=p.get("type"),
                        text=p.get("text"),
                        created_at=p.get("created_at"),
                        reply_count=0,
                        repost_count=0,
                        quote_count=0,
                        like_count=0,
                        engagement_score=0,
                        raw_data=None,
                    )
                    for p in posts
                ]
                self._hydrate_post_engagement(temp_items)
                for i, it in enumerate(temp_items):
                    if i < len(posts):
                        posts[i]["engagement"] = {
                            "likes": int(it.like_count or 0),
                            "reposts": int(it.repost_count or 0),
                            "replies": int(it.reply_count or 0),
                            "quotes": int(it.quote_count or 0),
                            "score": float(it.engagement_score or 0.0),
                        }
        except Exception:
            # Best-effort; leave zeros if hydration fails here
            pass

        # Determine which categories to include (CAR paths work with dicts, not ContentItem)
        cats = categories or {"posts", "likes", "reposts"}
        export_data = {
            "handle": handle,
            "did": did,
            "export_time": datetime.now().isoformat(),
            "posts": posts if "posts" in cats else [],
            "likes": likes if "likes" in cats else [],
            "reposts": reposts if "reposts" in cats else [],
        }

        out = self.json_dir / f"{safe_name}.json"

        try:
            if out.exists():
                export_data = self._merge_backup_with_existing(out, export_data)

            with open(out, "w") as f:
                json.dump(export_data, f, indent=2)

            console.print(f"Imported and merged backup into {out}")
            return out

        except Exception as e:
            console.print(f"Failed to merge backup: {e}")
            return None

    def import_backup_replace(
        self,
        backup_path: Path,
        handle: Optional[str] = None,
        categories: Optional[set] = None,
    ) -> Optional[Path]:
        """Import records from a backup and REPLACE the handle's data export (no merge)."""
        try:
            data = Path(backup_path).read_bytes()
            car = CAR.from_bytes(data)
        except Exception as e:
            console.print(f"Failed to read backup: {e}")
            return None

        decoded = self._decode_car_blocks(car)
        cid_to_path, did = self._extract_backup_metadata(decoded)

        if not did:
            # Try to use current session DID or resolve from handle
            did = self.auth.current_did
            if not did and handle and self.auth.client:
                try:
                    prof = self.auth.client.get_profile(handle)
                    did = getattr(prof, "did", None)
                except Exception:
                    did = None
            if not did:
                console.print("No DID found in backup file - using placeholder")
                did = "did:plc:unknown"

        if not handle:
            try:
                prof = self.auth.client.get_profile(did)
                handle = getattr(prof, "handle", None)
            except Exception:
                handle = did.replace(":", "_")

        safe_name = (handle or "unknown").replace(".", "_")
        posts, likes, reposts = self._process_backup_records(
            decoded, cid_to_path, did, handle
        )

        # If authenticated, hydrate post engagement now so JSON persists counts
        try:
            if self.auth.is_authenticated() and posts:
                temp_items = [
                    ContentItem(
                        uri=p.get("uri"),
                        cid=p.get("cid"),
                        content_type=p.get("type"),
                        text=p.get("text"),
                        created_at=p.get("created_at"),
                        reply_count=0,
                        repost_count=0,
                        quote_count=0,
                        like_count=0,
                        engagement_score=0,
                        raw_data=None,
                    )
                    for p in posts
                ]
                self._hydrate_post_engagement(temp_items)
                for i, it in enumerate(temp_items):
                    if i < len(posts):
                        posts[i]["engagement"] = {
                            "likes": int(it.like_count or 0),
                            "reposts": int(it.repost_count or 0),
                            "replies": int(it.reply_count or 0),
                            "quotes": int(it.quote_count or 0),
                            "score": float(it.engagement_score or 0.0),
                        }
        except Exception:
            # Best-effort; leave zeros if hydration fails here
            pass

        # Determine which categories to include (CAR paths work with dicts, not ContentItem)
        cats = categories or {"posts", "likes", "reposts"}
        export_data = {
            "handle": handle,
            "did": did,
            "export_time": datetime.now().isoformat(),
            "posts": posts if "posts" in cats else [],
            "likes": likes if "likes" in cats else [],
            "reposts": reposts if "reposts" in cats else [],
        }

        out = self.json_dir / f"{safe_name}.json"

        try:
            with open(out, "w") as f:
                json.dump(export_data, f, indent=2)
            console.print(f"Imported backup and replaced {out}")
            return out
        except Exception as e:
            console.print(f"Failed to write data: {e}")
            return None

    def load_exported_data(self, export_path: Path) -> List[ContentItem]:
        """Load data from export file."""
        with open(export_path, "r") as f:
            raw_data = json.load(f)

        # Normalize historical export formats
        if isinstance(raw_data, list):
            data = {"posts": raw_data}
        elif isinstance(raw_data, dict):
            # Older exports sometimes nest under "data"
            if "posts" not in raw_data and isinstance(raw_data.get("data"), dict):
                data = raw_data["data"]
            else:
                data = raw_data
        else:
            data = {}

        def _coerce_list(value: Any) -> List[Dict[str, Any]]:
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
            return []

        posts_section = _coerce_list(
            data.get("posts")
            or data.get("processed_posts")
            or data.get("primary_items")
        )
        likes_section = _coerce_list(data.get("likes") or data.get("processed_likes"))
        reposts_section = _coerce_list(
            data.get("reposts") or data.get("processed_reposts")
        )

        content_items: List[ContentItem] = []

        for post_data in posts_section:
            if not isinstance(post_data, dict):
                continue

            engagement = post_data.get("engagement") or {}
            content_item = ContentItem(
                uri=post_data.get("uri"),
                cid=post_data.get("cid"),
                content_type=post_data.get("type", "post"),
                text=post_data.get("text"),
                created_at=post_data.get("created_at"),
                reply_count=int((engagement or {}).get("replies", 0) or 0),
                repost_count=int((engagement or {}).get("reposts", 0) or 0),
                quote_count=int((engagement or {}).get("quotes", 0) or 0),
                like_count=int((engagement or {}).get("likes", 0) or 0),
                engagement_score=float((engagement or {}).get("score", 0) or 0.0),
                raw_data=post_data.get("raw_data") or post_data,
            )
            # Always recalculate engagement score to ensure consistency
            content_item.update_engagement_score()
            content_items.append(content_item)

        for like in likes_section:
            if not isinstance(like, dict):
                continue

            like_item = ContentItem(
                uri=like.get("uri"),
                cid=like.get("cid"),
                content_type="like",
                text=None,
                created_at=like.get("created_at"),
                reply_count=0,
                repost_count=0,
                quote_count=0,
                like_count=0,
                engagement_score=0,
                raw_data={
                    "subject_uri": like.get("subject_uri"),
                    "subject_cid": like.get("subject_cid"),
                },
            )
            # Update engagement score (though it will be 0 for likes)
            like_item.update_engagement_score()
            content_items.append(like_item)

        for rp in reposts_section:
            if not isinstance(rp, dict):
                continue

            repost_item = ContentItem(
                uri=rp.get("uri"),
                cid=rp.get("cid"),
                content_type="repost",
                text=None,
                created_at=rp.get("created_at"),
                reply_count=0,
                repost_count=0,
                quote_count=0,
                like_count=0,
                engagement_score=0,
                raw_data={
                    "subject_uri": rp.get("subject_uri"),
                    "subject_cid": rp.get("subject_cid"),
                    "self_repost": rp.get("self_repost", False),
                },
            )
            # Update engagement score (though it will be 0 for reposts)
            repost_item.update_engagement_score()
            content_items.append(repost_item)

        return content_items

    def get_user_files(self, handle: str, file_type: str = "json") -> List[Path]:
        """Get files belonging to a specific user handle."""
        if not handle:
            return []

        safe_handle = handle.replace(".", "_")

        if file_type == "json":
            directory = self.json_dir
            pattern = f"{safe_handle}.json"
        elif file_type == "backup":
            directory = self.backups_dir
            pattern = f"{safe_handle}*.car"  # Include timestamped backups
        else:
            return []

        # Find files that match the user's handle
        user_files = []
        for file_path in directory.glob("*.json" if file_type == "json" else "*.car"):
            if self._file_belongs_to_user(file_path, handle):
                user_files.append(file_path)

        return sorted(user_files)

    def _file_belongs_to_user(self, file_path: Path, handle: str) -> bool:
        """Check if a file belongs to the specified user."""
        if not handle:
            return False

        safe_handle = handle.replace(".", "_")
        filename = file_path.name

        # Check filename patterns
        if filename.startswith(f"{safe_handle}.") or filename.startswith(
            f"{safe_handle}_"
        ):
            return True

        # For JSON files, also check the content handle
        if file_path.suffix == ".json":
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    file_handle = data.get("handle", "")
                    return (
                        file_handle == handle
                        or file_handle.replace(".", "_") == safe_handle
                    )
            except Exception:
                pass

        return False

    def validate_file_access(self, file_path: Path, current_handle: str) -> bool:
        """Validate that the current user can access this file."""
        if not current_handle:
            console.print("Authentication required to access files")
            return False

        if not self._file_belongs_to_user(file_path, current_handle):
            console.print(f"Access denied: File does not belong to @{current_handle}")
            console.print(f"Security: Users can only access their own data files")
            return False

        return True

    def _fetch_posts_records(
        self, did: str, max_items: int, progress_callback=None
    ) -> List[ContentItem]:
        """Iterate app.bsky.feed.post records from the user's repo using cursors."""
        items: List[ContentItem] = []
        cursor: Optional[str] = None
        per_page = max(1, min(100, self.settings.records_page_size))

        while len(items) < max_items:
            try:
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "app.bsky.feed.post",
                        "limit": min(per_page, max_items - len(items)),
                        "cursor": cursor,
                    }
                )

                records = getattr(resp, "records", []) or []
                if not records:
                    break

                for rec in records:
                    value = getattr(rec, "value", None)
                    text = getattr(value, "text", None) if value is not None else None
                    created_at = (
                        getattr(value, "created_at", None)
                        if value is not None
                        else None
                    ) or (value.get("createdAt") if isinstance(value, dict) else None)
                    reply = (
                        getattr(value, "reply", None) if value is not None else None
                    ) or (value.get("reply") if isinstance(value, dict) else None)

                    item = ContentItem(
                        uri=getattr(rec, "uri", None),
                        cid=getattr(rec, "cid", None),
                        content_type="reply" if reply else "post",
                        text=text,
                        created_at=created_at,
                        reply_count=0,
                        repost_count=0,
                        quote_count=0,
                        like_count=0,
                        engagement_score=0,
                        raw_data=None,
                    )
                    item.update_engagement_score()
                    items.append(item)

                    if len(items) >= max_items:
                        break

                if progress_callback:
                    try:
                        progress_callback(len(items))
                    except Exception as e:
                        # Better error reporting for debugging
                        if "not callable" in str(e):
                            console.print(
                                f"[red]Progress callback error: {type(progress_callback)} is not callable[/red]"
                            )
                        pass

                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break

            except Exception as e:
                console.print(f"[yellow]Warning: error paging posts: {e}[/yellow]")
                break

        return items

    def hydrate_items(self, items: List[ContentItem], collect_details: bool = False):
        """Update engagement metrics for content items (optionally with detail hydration).

        This is primarily used after importing from .car where engagement is zeroed.
        Shows user-facing progress for a better experience. When collect_details=True,
        additional API calls are executed to gather likes/reposts/quotes/replies data.
        """
        try:
            if not items:
                console.print("[yellow]hydrate_items called with empty items list[/yellow]")
                return
                
            console.print(f"[cyan]Starting hydration for {len(items)} items[/cyan]")

            # First, always update engagement scores with current data
            for item in items:
                item.update_engagement_score()

            # Ensure authentication before starting interactive progress UI
            if not self.auth.is_authenticated():
                console.print("[yellow]Re-authentication required for engagement hydration[/]")
                if not self.auth.ensure_authentication():
                    console.print("[dim]Using existing engagement data[/dim]")
                    return

            posts_and_replies = [
                it for it in items if it.content_type in ("post", "reply")
            ]
            reposts = (
                [it for it in items if it.content_type == "repost"]
                if self.settings.use_subject_engagement_for_reposts
                else []
            )
            
            console.print(f"[dim]Found {len(posts_and_replies)} posts/replies and {len(reposts)} reposts to hydrate[/dim]")

            # Display a compact, transient progress UI for hydration steps
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
                console=console,
            ) as progress:
                reauth_needed = False
                # Posts/replies engagement hydration
                if posts_and_replies:
                    total_posts = len(posts_and_replies)
                    task_posts = progress.add_task(
                        f"Updating engagement (posts/replies) 0/{total_posts}",
                        total=total_posts,
                    )

                    def make_cb_posts(total: int):
                        def _cb(completed: int):
                            progress.update(
                                task_posts,
                                completed=min(completed, total),
                                description=f"Updating engagement (posts/replies) {completed}/{total}",
                            )

                        return _cb

                    try:
                        self._hydrate_post_engagement(
                            posts_and_replies,
                            progress_callback=make_cb_posts(total_posts),
                        )
                    except AuthenticationError:
                        reauth_needed = True

                if collect_details and posts_and_replies and not reauth_needed:
                    total_details = len(posts_and_replies)
                    task_details = progress.add_task(
                        f"Collecting interaction details 0/{total_details}",
                        total=total_details,
                    )

                    def make_cb_details(total: int):
                        def _cb(completed: int):
                            progress.update(
                                task_details,
                                completed=min(completed, total),
                                description=f"Collecting interaction details {completed}/{total}",
                            )

                        return _cb

                    try:
                        self._hydrate_post_interaction_details(
                            posts_and_replies,
                            progress_callback=make_cb_details(total_details),
                        )
                    except AuthenticationError:
                        reauth_needed = True

                # Repost subject hydration (optional)
                if reposts and not reauth_needed:
                    total_reposts = len(reposts)
                    task_reposts = progress.add_task(
                        f"Updating subject metrics (reposts) 0/{total_reposts}",
                        total=total_reposts,
                    )

                    def make_cb_reposts(total: int):
                        def _cb(completed: int):
                            progress.update(
                                task_reposts,
                                completed=min(completed, total),
                                description=f"Updating subject metrics (reposts) {completed}/{total}",
                            )

                        return _cb

                    try:
                        self._hydrate_repost_subject_engagement(
                            reposts, progress_callback=make_cb_reposts(total_reposts)
                        )
                    except AuthenticationError:
                        reauth_needed = True

                # Final engagement score recalculation for all items (only if no reauth needed)
                if not reauth_needed:
                    all_items = posts_and_replies + reposts
                    if all_items:
                        task_scores = progress.add_task(
                            "Finalizing engagement scores", total=len(all_items)
                        )
                        for i, item in enumerate(all_items):
                            item.update_engagement_score()
                            progress.update(task_scores, completed=i + 1)

                # If reauth is needed, fall through and handle outside of progress UI
                if reauth_needed:
                    raise AuthenticationError("Hydration requires re-authentication")

        except Exception as e:
            # Best-effort update; show concise warning
            console.print(f"[yellow]Warning: engagement refresh skipped: {e}[/yellow]")
            # Still try to update engagement scores using current data
            try:
                for item in items:
                    item.update_engagement_score()
            except Exception:
                pass
            # If auth-related, attempt one-time reauth and retry hydration once
            if isinstance(e, AuthenticationError):
                # Prompt outside of progress UI
                console.print("[yellow]Authentication required during hydration - please log in[/]")
                if self.auth.ensure_authentication():
                    # Retry once (no recursion loops)
                    try:
                        self.hydrate_items(items, collect_details=collect_details)
                    except Exception:
                        # Give up silently after one retry
                        pass

    def _fetch_likes_records(
        self, did: str, max_items: int, progress_callback=None
    ) -> List[ContentItem]:
        """Iterate app.bsky.feed.like records from the user's repo using cursors."""
        items: List[ContentItem] = []
        cursor: Optional[str] = None
        per_page = max(1, min(100, self.settings.records_page_size))

        while len(items) < max_items:
            try:
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "app.bsky.feed.like",
                        "limit": min(per_page, max_items - len(items)),
                        "cursor": cursor,
                    }
                )

                records = getattr(resp, "records", []) or []
                if not records:
                    break

                for rec in records:
                    value = getattr(rec, "value", None)
                    subject = (
                        getattr(value, "subject", None) if value is not None else None
                    ) or (value.get("subject") if isinstance(value, dict) else None)
                    subject_uri = (
                        getattr(subject, "uri", None)
                        if subject is not None
                        else (subject.get("uri") if isinstance(subject, dict) else None)
                    )
                    subject_cid = (
                        getattr(subject, "cid", None)
                        if subject is not None
                        else (subject.get("cid") if isinstance(subject, dict) else None)
                    )
                    created_at = (
                        getattr(value, "created_at", None)
                        if value is not None
                        else None
                    ) or (value.get("createdAt") if isinstance(value, dict) else None)

                    item = ContentItem(
                        uri=getattr(rec, "uri", None),
                        cid=getattr(rec, "cid", None),
                        content_type="like",
                        text=None,
                        created_at=created_at,
                        reply_count=0,
                        repost_count=0,
                        quote_count=0,
                        like_count=0,
                        engagement_score=0,
                        raw_data={
                            "subject_uri": subject_uri,
                            "subject_cid": subject_cid,
                        },
                    )
                    item.update_engagement_score()
                    items.append(item)

                    if len(items) >= max_items:
                        break

                if progress_callback:
                    try:
                        progress_callback(len(items))
                    except Exception as e:
                        # Better error reporting for debugging
                        if "not callable" in str(e):
                            console.print(
                                f"[red]Progress callback error: {type(progress_callback)} is not callable[/red]"
                            )
                        pass

                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break

            except Exception as e:
                console.print(f"[yellow]Warning: error paging likes: {e}[/yellow]")
                break

        return items

    def _fetch_reposts_records(
        self, did: str, max_items: int, progress_callback=None
    ) -> List[ContentItem]:
        """Iterate app.bsky.feed.repost records from the user's repo using cursors."""
        items: List[ContentItem] = []
        cursor: Optional[str] = None
        per_page = max(1, min(100, self.settings.records_page_size))

        while len(items) < max_items:
            try:
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": "app.bsky.feed.repost",
                        "limit": min(per_page, max_items - len(items)),
                        "cursor": cursor,
                    }
                )

                records = getattr(resp, "records", []) or []
                if not records:
                    break

                for rec in records:
                    value = getattr(rec, "value", None)
                    subject = (
                        getattr(value, "subject", None) if value is not None else None
                    ) or (value.get("subject") if isinstance(value, dict) else None)
                    subject_uri = (
                        getattr(subject, "uri", None)
                        if subject is not None
                        else (subject.get("uri") if isinstance(subject, dict) else None)
                    )
                    subject_cid = (
                        getattr(subject, "cid", None)
                        if subject is not None
                        else (subject.get("cid") if isinstance(subject, dict) else None)
                    )
                    created_at = (
                        getattr(value, "created_at", None)
                        if value is not None
                        else None
                    ) or (value.get("createdAt") if isinstance(value, dict) else None)

                    # Parse repo DID from at://did:plc:.../collection/rkey safely
                    subj_repo = None
                    if (
                        subject_uri
                        and isinstance(subject_uri, str)
                        and subject_uri.startswith("at://")
                    ):
                        try:
                            parts = subject_uri.split("/")
                            if len(parts) > 2:
                                subj_repo = parts[2]
                        except Exception:
                            subj_repo = None
                    self_repost = subj_repo == did

                    item = ContentItem(
                        uri=getattr(rec, "uri", None),
                        cid=getattr(rec, "cid", None),
                        content_type="repost",
                        text=None,
                        created_at=created_at,
                        reply_count=0,
                        repost_count=0,
                        quote_count=0,
                        like_count=0,
                        engagement_score=0,
                        raw_data={
                            "subject_uri": subject_uri,
                            "subject_cid": subject_cid,
                            "self_repost": self_repost,
                        },
                    )
                    item.update_engagement_score()
                    items.append(item)

                    if len(items) >= max_items:
                        break

                if progress_callback:
                    try:
                        progress_callback(len(items))
                    except Exception as e:
                        # Better error reporting for debugging
                        if "not callable" in str(e):
                            console.print(
                                f"[red]Progress callback error: {type(progress_callback)} is not callable[/red]"
                            )
                        pass

                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break

            except Exception as e:
                console.print(f"[yellow]Warning: error paging reposts: {e}[/yellow]")
                break

        return items

    def _hydrate_post_engagement(
        self, items: List[ContentItem], progress_callback=None
    ):
        """Fetch like/repost/reply counts for posts/replies via AppView get_posts in batches.

        Args:
            items: Items to hydrate
            progress_callback: Optional callable taking the cumulative number of hydrated items
        """
        try:
            uris = [it.uri for it in items if it.uri]
            if not uris:
                console.print("[yellow]No URIs found in items for hydration[/yellow]")
                return
                
            console.print(f"[dim]Extracted {len(uris)} URIs for hydration[/dim]")
            if uris:
                console.print(f"[dim]Sample full URIs: {uris[:3]}[/dim]")

            batch_size = max(1, min(25, self.settings.hydrate_batch_size))
            uri_batches = [
                uris[i : i + batch_size] for i in range(0, len(uris), batch_size)
            ]
            index = {it.uri: it for it in items if it.uri}

            processed = 0

            for batch in uri_batches:

                try:
                    # Ensure we have a client; require authentication to proceed
                    if not self.auth.is_authenticated():
                        raise AuthenticationError("Authentication required for hydration")
                    
                    console.print(
                        f"[dim]Making API call for batch of {len(batch)} URIs: {batch[:3]}... (showing first 3)[/dim]"
                    )

                    def _call():
                        client = self.auth.client
                        if client is None:
                            raise AuthenticationError("Client not available for hydration")
                        return client.get_posts(uris=batch)

                    # Use call_with_reauth so expired sessions retry silently
                    resp = self.auth.call_with_reauth(_call)

                    # Validate response structure
                    if not resp or not hasattr(resp, "posts"):
                        console.print(f"[yellow]Invalid response structure for batch: {type(resp)}[/yellow]")
                        continue

                    posts = getattr(resp, "posts", None)
                    if not posts:
                        console.print(f"[yellow]No posts in response for batch of {len(batch)} URIs[/yellow]")
                        continue

                    console.print(f"[dim]Processing {len(posts)} posts from API response[/dim]")

                    for p in posts:
                        # Validate post object structure
                        if not p or not hasattr(p, "uri"):
                            continue

                        uri = getattr(p, "uri", None)
                        if not uri:
                            continue

                        it = index.get(uri)
                        if not it:
                            console.print(f"[yellow]Warning: URI {uri} not found in index[/yellow]")
                            continue

                        # Extract engagement counts with debugging
                        likes = int(getattr(p, "like_count", 0) or 0)
                        reposts = int(getattr(p, "repost_count", 0) or 0)
                        replies = int(getattr(p, "reply_count", 0) or 0)
                        quotes = int(getattr(p, "quote_count", 0) or 0)
                        
                        # Debug: Show available attributes if no engagement found
                        if likes == 0 and reposts == 0 and replies == 0 and quotes == 0:
                            attrs = [attr for attr in dir(p) if not attr.startswith('_')]
                            console.print(f"[yellow]No engagement found for {uri[:50]}..., available attrs: {attrs}[/yellow]")

                        # Debug: Log engagement data extraction
                        if likes > 0 or reposts > 0 or replies > 0 or quotes > 0:
                            console.print(
                                f"[dim]Found engagement for {uri[:50]}...: likes={likes}, reposts={reposts}, replies={replies}, quotes={quotes}[/dim]"
                            )

                        it.like_count = likes
                        it.repost_count = reposts
                        it.reply_count = replies
                        it.quote_count = quotes
                        it.engagement_score = calculate_engagement_score(likes, reposts, replies)

                    processed += len(batch)
                    if callable(progress_callback):
                        try:
                            progress_callback(processed)
                        except Exception:
                            pass
                except AuthenticationError:
                    raise
                except Exception as e:
                    console.print(
                        f"[yellow]Hydration failed for batch (URIs: {len(batch)}): {str(e)[:100]}[/]"
                    )
                    processed += len(batch)
                    if callable(progress_callback):
                        try:
                            progress_callback(processed)
                        except Exception:
                            pass
        except AuthenticationError:
            # Re-raise authentication errors to be handled by caller
            raise
        except Exception as e:
            # Log other unexpected errors but don't swallow them completely
            console.print(f"[red]Unexpected error during hydration: {str(e)[:100]}[/red]")
            raise

    @staticmethod
    def _extract_post_text(record: Any) -> Optional[str]:
        """Best-effort extraction of text content from a post record."""
        if record is None:
            return None
        if hasattr(record, "text"):
            return getattr(record, "text", None)
        if isinstance(record, dict):
            return record.get("text")
        return None

    def _fetch_post_likes(self, uri: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            remaining = limit - len(results) if limit else None
            page_limit = None
            if remaining is not None:
                if remaining <= 0:
                    break
                page_limit = min(100, remaining)

            def _call():
                client = self.auth.client
                if client is None:
                    raise AuthenticationError("Client not available for get_likes")
                kwargs = {"uri": uri, "cursor": cursor}
                if page_limit:
                    kwargs["limit"] = page_limit
                return client.get_likes(**kwargs)  # type: ignore[attr-defined]

            resp = self.auth.call_with_reauth(_call)
            likes = getattr(resp, "likes", None)
            if not likes:
                break

            for entry in likes:
                actor = getattr(entry, "actor", None)
                results.append(
                    {
                        "handle": getattr(actor, "handle", None),
                        "did": getattr(actor, "did", None),
                        "display_name": getattr(actor, "display_name", None),
                        "created_at": getattr(entry, "created_at", None),
                    }
                )
                if limit and len(results) >= limit:
                    break

            cursor = getattr(resp, "cursor", None)
            if not cursor or (limit and len(results) >= limit):
                break

        return results

    def _fetch_post_reposted_by(self, uri: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            remaining = limit - len(results) if limit else None
            page_limit = None
            if remaining is not None:
                if remaining <= 0:
                    break
                page_limit = min(100, remaining)

            def _call():
                client = self.auth.client
                if client is None:
                    raise AuthenticationError("Client not available for get_reposted_by")
                kwargs = {"uri": uri, "cursor": cursor}
                if page_limit:
                    kwargs["limit"] = page_limit
                return client.get_reposted_by(**kwargs)  # type: ignore[attr-defined]

            resp = self.auth.call_with_reauth(_call)
            reposted_by = getattr(resp, "reposted_by", None)
            if not reposted_by:
                break

            for actor in reposted_by:
                results.append(
                    {
                        "handle": getattr(actor, "handle", None),
                        "did": getattr(actor, "did", None),
                        "display_name": getattr(actor, "display_name", None),
                        "avatar": getattr(actor, "avatar", None),
                    }
                )
                if limit and len(results) >= limit:
                    break

            cursor = getattr(resp, "cursor", None)
            if not cursor or (limit and len(results) >= limit):
                break

        return results

    def _fetch_post_quotes(self, uri: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None

        while True:
            remaining = limit - len(results) if limit else None
            page_limit = None
            if remaining is not None:
                if remaining <= 0:
                    break
                page_limit = min(25, remaining)

            def _call():
                client = self.auth.client
                if client is None:
                    raise AuthenticationError("Client not available for get_quotes")
                params: Dict[str, Any] = {"uri": uri, "cursor": cursor}
                if page_limit:
                    params["limit"] = page_limit
                return client.app.bsky.feed.get_quotes(params)

            resp = self.auth.call_with_reauth(_call)
            posts = getattr(resp, "posts", None)
            if not posts:
                break

            for post_view in posts:
                author = getattr(post_view, "author", None)
                results.append(
                    {
                        "uri": getattr(post_view, "uri", None),
                        "cid": getattr(post_view, "cid", None),
                        "handle": getattr(author, "handle", None),
                        "did": getattr(author, "did", None),
                        "display_name": getattr(author, "display_name", None),
                        "text": self._extract_post_text(getattr(post_view, "record", None)),
                        "indexed_at": getattr(post_view, "indexed_at", None),
                    }
                )
                if limit and len(results) >= limit:
                    break

            cursor = getattr(resp, "cursor", None)
            if not cursor or (limit and len(results) >= limit):
                break

        return results

    def _fetch_post_replies(self, uri: str, limit: int) -> List[Dict[str, Any]]:
        def _collect(node, container):
            replies = getattr(node, "replies", None) or []
            for reply in replies:
                if limit and len(container) >= limit:
                    return
                if hasattr(reply, "post"):
                    post_view = getattr(reply, "post", None)
                    author = getattr(post_view, "author", None)
                    container.append(
                        {
                            "uri": getattr(post_view, "uri", None),
                            "cid": getattr(post_view, "cid", None),
                            "handle": getattr(author, "handle", None),
                            "did": getattr(author, "did", None),
                            "display_name": getattr(author, "display_name", None),
                            "text": self._extract_post_text(getattr(post_view, "record", None)),
                            "indexed_at": getattr(post_view, "indexed_at", None),
                        }
                    )
                    if limit and len(container) >= limit:
                        return
                    _collect(reply, container)

        def _call():
            client = self.auth.client
            if client is None:
                raise AuthenticationError("Client not available for get_post_thread")
            return client.get_post_thread(uri=uri, depth=2)

        resp = self.auth.call_with_reauth(_call)
        root = getattr(resp, "thread", None)
        collected: List[Dict[str, Any]] = []
        if root and hasattr(root, "post"):
            _collect(root, collected)
        if limit:
            return collected[:limit]
        return collected

    def _hydrate_post_interaction_details(
        self,
        items: List[ContentItem],
        progress_callback=None,
    ) -> None:
        """Populate detailed interaction lists (likes, reposts, quotes, replies)."""

        if not items:
            return

        if not self.auth.is_authenticated() or not self.auth.client:
            raise AuthenticationError("Authentication required for interaction hydration")

        detail_limit = max(self.settings.interaction_detail_limit, 0)

        for idx, item in enumerate(items, start=1):
            if not item.uri:
                continue

            try:
                likes = self._fetch_post_likes(item.uri, detail_limit)
                reposts = self._fetch_post_reposted_by(item.uri, detail_limit)
                quotes = self._fetch_post_quotes(item.uri, detail_limit)
                replies = self._fetch_post_replies(item.uri, detail_limit)
            except AuthenticationError:
                raise
            except Exception as exc:
                console.print(
                    f"[yellow]Interaction enrichment failed for {item.uri[:50]}...: {str(exc)[:80]}[/yellow]"
                )
                continue

            raw = item.raw_data or {}
            raw.update(
                {
                    "likes": likes,
                    "reposted_by": reposts,
                    "quotes": quotes,
                    "replies": replies,
                }
            )
            item.raw_data = raw

            # Update counts when detailed data is richer than existing values
            item.reply_count = max(item.reply_count or 0, len(replies))
            item.quote_count = max(item.quote_count or 0, len(quotes))

            if callable(progress_callback):
                try:
                    progress_callback(idx)
                except Exception:
                    pass

    def _hydrate_repost_subject_engagement(
        self, items: List[ContentItem], progress_callback=None
    ):
        """Fetch subject post counters for repost items and attach to raw_data for display.

        Args:
            items: Repost items whose subjects to hydrate
            progress_callback: Optional callable taking the cumulative number of hydrated items
        """
        try:
            uris = []
            index = {}

            for it in items:
                subj = (it.raw_data or {}).get("subject_uri")
                if subj:
                    uris.append(subj)
                    index[subj] = it

            if not uris:
                return

            batch_size = max(1, min(25, self.settings.hydrate_batch_size))
            uri_batches = [
                uris[i : i + batch_size] for i in range(0, len(uris), batch_size)
            ]

            processed = 0

            for batch in uri_batches:

                try:
                    client = self.auth.client
                    if client is None:
                        raise AuthenticationError("Authentication required for repost hydration")

                    # Direct API call without automatic re-auth to avoid loops
                    resp = client.get_posts(uris=batch)

                    # Validate response structure
                    if not resp or not hasattr(resp, "posts"):
                        continue

                    posts = getattr(resp, "posts", None)
                    if not posts:
                        continue

                    for p in posts:
                        # Validate post object structure
                        if not p or not hasattr(p, "uri"):
                            continue

                        uri = getattr(p, "uri", None)
                        if not uri:
                            continue

                        it = index.get(uri)
                        if not it:
                            continue

                        rd = it.raw_data or {}
                        rd["subject_like_count"] = int(getattr(p, "like_count", 0) or 0)
                        rd["subject_repost_count"] = int(
                            getattr(p, "repost_count", 0) or 0
                        )
                        rd["subject_reply_count"] = int(
                            getattr(p, "reply_count", 0) or 0
                        )
                        it.raw_data = rd

                    processed += len(batch)
                    if callable(progress_callback):
                        try:
                            progress_callback(processed)
                        except Exception:
                            pass
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(s in error_msg for s in ["auth", "unauthorized", "token", "expired", "forbidden"]):
                        raise AuthenticationError("Authentication expired during repost hydration")
                    else:
                        # Log other types of hydration errors for debugging
                        console.print(
                            f"[yellow]Repost hydration failed for batch (URIs: {len(batch)}): {str(e)[:100]}[/]"
                        )
                        # Still increment processed count for failed batch to continue progress tracking
                        processed += len(batch)
                        if callable(progress_callback):
                            try:
                                progress_callback(processed)
                            except Exception:
                                pass
                    # Continue with remaining batches using existing data
        except AuthenticationError:
            # Re-raise authentication errors to be handled by caller
            raise
        except Exception as e:
            # Log other unexpected errors but don't swallow them completely
            console.print(f"[red]Unexpected error during repost hydration: {str(e)[:100]}[/red]")
            raise

    def _apply_date_filter(self, posts, likes, reposts, date_start, date_end):
        """Apply date filtering to content items."""
        sd = parse_datetime(date_start)
        ed = parse_datetime(date_end)

        def within(it: ContentItem):
            if not (sd or ed):
                return True
            dt = parse_datetime(it.created_at)
            if dt is None:
                return False
            if sd and dt < sd:
                return False
            if ed and dt > ed:
                return False
            return True

        if sd or ed:
            posts = [it for it in posts if within(it)]
            likes = [it for it in likes if within(it)]
            reposts = [it for it in reposts if within(it)]

        return posts, likes, reposts

    def _sort_by_date(self, posts, likes, reposts):
        """Sort items by date according to fetch_order setting."""

        def _to_dt(x):
            return parse_datetime(x.created_at, datetime.min)

        posts.sort(key=_to_dt)
        likes.sort(key=_to_dt)
        reposts.sort(key=_to_dt)

    def _build_export_data(self, handle, did, posts, likes, reposts, cats):
        """Build the export data structure."""
        export_data = {
            "handle": handle,
            "did": did,
            "export_time": datetime.now().isoformat(),
            "posts": (
                [
                    {
                        "uri": item.uri,
                        "cid": item.cid,
                        "type": item.content_type,
                        "text": item.text,
                        "created_at": item.created_at,
                        "engagement": {
                            "likes": item.like_count,
                            "reposts": item.repost_count,
                            "replies": item.reply_count,
                            "quotes": item.quote_count,
                            "score": item.engagement_score,
                        },
                        "raw_data": item.raw_data,
                    }
                    for item in posts
                ]
                if "posts" in cats
                else []
            ),
            "likes": (
                [
                    {
                        "uri": item.uri,
                        "cid": item.cid,
                        "type": "like",
                        "created_at": item.created_at,
                        "subject_uri": (item.raw_data or {}).get("subject_uri"),
                        "subject_cid": (item.raw_data or {}).get("subject_cid"),
                    }
                    for item in likes
                ]
                if "likes" in cats
                else []
            ),
            "reposts": (
                [
                    {
                        "uri": item.uri,
                        "cid": item.cid,
                        "type": "repost",
                        "created_at": item.created_at,
                        "subject_uri": (item.raw_data or {}).get("subject_uri"),
                        "subject_cid": (item.raw_data or {}).get("subject_cid"),
                        "self_repost": (item.raw_data or {}).get("self_repost", False),
                    }
                    for item in reposts
                ]
                if "reposts" in cats
                else []
            ),
        }

        return export_data

    def _merge_with_existing(self, export_path, export_data):
        """Merge export data with existing file."""
        try:
            with open(export_path, "r") as f:
                old = json.load(f)
        except Exception:
            old = {}

        export_data["posts"] = merge_content_items(
            "posts",
            export_data.get("posts", []),
            old.get("posts", []),
            self.settings.fetch_order,
        )
        export_data["likes"] = merge_content_items(
            "likes",
            export_data.get("likes", []),
            old.get("likes", []),
            self.settings.fetch_order,
        )
        export_data["reposts"] = merge_content_items(
            "reposts",
            export_data.get("reposts", []),
            old.get("reposts", []),
            self.settings.fetch_order,
        )

        return export_data

    def _decode_car_blocks(self, car):
        """Decode CAR blocks into CBOR."""
        decoded = {}
        blocks = getattr(car, "blocks", None)
        it = []

        # Skip block counting to avoid hanging on large CAR files
        block_count = "unknown"  # Block counting removed to prevent hanging
        # console.print(f"Debug: Backup contains {block_count} total objects")

        if isinstance(blocks, dict):
            it = list(blocks.items())
        elif hasattr(car, "blocks"):
            # Backup objects typically have an iterator for blocks
            # Use car.blocks directly in the processing loop to avoid pre-iteration
            # This prevents hanging on large CAR files
            it = car.blocks
        elif isinstance(blocks, (list, tuple)):
            for b in blocks:
                try:
                    if isinstance(b, tuple) and len(b) == 2:
                        it.append((b[0], b[1]))
                    elif hasattr(b, "cid") and hasattr(b, "bytes"):
                        it.append((getattr(b, "cid"), getattr(b, "bytes")))
                    elif isinstance(b, dict) and "cid" in b and "bytes" in b:
                        it.append((b["cid"], b["bytes"]))
                except Exception:
                    continue

        # console.print(f"Debug: Found {len(it)} path mappings")

        if cbor_decode is None:
            console.print(
                "No CBOR decoder available. Install libipld or cbor2: pip install libipld"
            )
            return {}

        # Show progress while decoding blocks
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            # Use None for total to avoid counting items (prevents hanging)
            task = progress.add_task(f"Decoding backup blocks...", total=None)
            processed_count = 0
            for item in it:
                processed_count += 1
                if processed_count % 100 == 0:
                    progress.update(task, description=f"Decoding backup blocks... ({processed_count} processed)")
                
                try:
                    # Handle different iterator types
                    if isinstance(item, tuple) and len(item) == 2:
                        cid, block = item
                    elif hasattr(item, "cid") and hasattr(item, "data"):
                        cid, block = item.cid, item.data
                    elif hasattr(item, "cid") and hasattr(item, "bytes"):
                        cid, block = item.cid, item.bytes
                    else:
                        # console.print(f"Debug: Unknown item format: {type(item)}")
                        continue
                    
                    # Handle different block data formats
                    if isinstance(block, dict):
                        decoded[str(cid)] = block
                    elif isinstance(block, (bytes, bytearray)):
                        decoded[str(cid)] = cbor_decode(block)
                    else:
                        if hasattr(block, "bytes"):
                            decoded[str(cid)] = cbor_decode(block.bytes)
                        elif hasattr(block, "data"):
                            decoded[str(cid)] = cbor_decode(block.data)
                        else:
                            # console.print(f"Debug: Unknown block format for {cid}: {type(block)}")
                            continue
                except Exception as e:
                    # console.print(f"Debug: Failed to decode block: {e}")
                    pass

        return decoded

    def _extract_backup_metadata(self, decoded):
        """Extract DID and CID-to-path mapping from backup commit operations."""
        cid_to_path = {}
        did = None

        for obj in decoded.values():
            if isinstance(obj, dict) and obj.get("$type") in (
                "com.atproto.repo.commit",
                "com.atproto.repo#commit",
            ):
                did = obj.get("did") or obj.get("repo") or did
                for op in obj.get("ops", []) or []:
                    c = op.get("cid")
                    p = op.get("path")
                    if c and p:
                        cid_to_path[str(c)] = p

        return cid_to_path, did

    def _process_backup_records(self, decoded, cid_to_path, did, handle=None):
        """Process backup records into posts, likes, and reposts."""
        posts = []
        likes = []
        reposts = []

        # Try to get the real DID from the authenticated client if we have a placeholder
        effective_did = did
        if did == "did:plc:unknown" and handle and self.auth.client:
            try:
                profile = self.auth.client.get_profile(handle)
                effective_did = profile.did
                console.print(f"Resolved real DID: {effective_did}")
            except Exception as e:
                console.print(f"Could not resolve DID for {handle}: {e}")
                effective_did = did  # Keep the placeholder
        elif not effective_did:
            effective_did = "did:plc:unknown"

        record_types = set(
            obj.get("$type")
            for obj in decoded.values()
            if isinstance(obj, dict) and obj.get("$type")
        )
        no_type_count = sum(
            1
            for obj in decoded.values()
            if isinstance(obj, dict) and not obj.get("$type")
        )
        no_path_count = sum(
            1
            for cid, obj in decoded.items()
            if isinstance(obj, dict)
            and obj.get("$type")
            and not cid_to_path.get(str(cid))
        )
        other_types_count = sum(
            1 for obj in decoded.values() if not isinstance(obj, dict)
        )

        # console.print(f"Debug: Record types found: {record_types}")
        # console.print(f"Debug: Skipped - no type: {no_type_count}, no path: {no_path_count}, other types: {other_types_count}")

        if not record_types and len(decoded) > 0:
            # console.print("Debug: Backup file contains data but no recognizable records")
            # console.print("Debug: This may be an empty account or a different data format")
            pass

        # Show progress while extracting records
        total_decoded = len(decoded)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Extracting records 0/{total_decoded}", total=total_decoded or 1
            )
            for cid, obj in decoded.items():
                try:
                    if not isinstance(obj, dict):
                        continue

                    rtype = obj.get("$type")
                    path = cid_to_path.get(str(cid))

                    # Handle CAR files without commit records (path mapping)
                    if not path and rtype:
                        if rtype == "app.bsky.feed.post":
                            path = f"app.bsky.feed.post/{str(cid)}"
                        elif rtype == "app.bsky.feed.like":
                            path = f"app.bsky.feed.like/{str(cid)}"
                        elif rtype == "app.bsky.feed.repost":
                            path = f"app.bsky.feed.repost/{str(cid)}"
                        else:
                            continue  # Skip other record types

                    if not path or not rtype or "/" not in path:
                        continue

                    collection, rkey = path.split("/", 1)
                    uri = f"at://{effective_did}/{collection}/{rkey}"
                    created = obj.get("createdAt") or obj.get("created_at")

                    if rtype == "app.bsky.feed.post":
                        is_reply = bool(obj.get("reply"))
                        posts.append(
                            {
                                "uri": uri,
                                "cid": cid,
                                "type": "reply" if is_reply else "post",
                                "text": obj.get("text"),
                                "created_at": created,
                                "engagement": {
                                    "likes": 0,
                                    "reposts": 0,
                                    "replies": 0,
                                    "score": 0,
                                },
                                "raw_data": None,
                            }
                        )
                    elif rtype == "app.bsky.feed.like":
                        subj = obj.get("subject") or {}
                        likes.append(
                            {
                                "uri": uri,
                                "cid": cid,
                                "type": "like",
                                "created_at": created,
                                "subject_uri": subj.get("uri"),
                                "subject_cid": subj.get("cid"),
                            }
                        )
                    elif rtype == "app.bsky.feed.repost":
                        subj = obj.get("subject") or {}
                        reposts.append(
                            {
                                "uri": uri,
                                "cid": cid,
                                "type": "repost",
                                "created_at": created,
                                "subject_uri": subj.get("uri"),
                                "subject_cid": subj.get("cid"),
                                "self_repost": False,
                            }
                        )
                finally:
                    progress.advance(task, 1)

        # console.print(f"Debug: Extracted {len(posts)} posts, {len(likes)} likes, {len(reposts)} reposts")

        if not posts and not likes and not reposts:
            console.print("This account appears to have no content yet")
            console.print("Try creating some posts, likes, or reposts on Bluesky first")

        return posts, likes, reposts

    def _merge_backup_with_existing(self, out, export_data):
        """Merge backup import data with existing data file."""
        try:
            with open(out, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

        export_data["posts"] = merge_content_items(
            "posts",
            export_data["posts"],
            existing.get("posts", []),
            self.settings.fetch_order,
        )
        export_data["likes"] = merge_content_items(
            "likes",
            export_data["likes"],
            existing.get("likes", []),
            self.settings.fetch_order,
        )
        export_data["reposts"] = merge_content_items(
            "reposts",
            export_data["reposts"],
            existing.get("reposts", []),
            self.settings.fetch_order,
        )

        return export_data

    def clear_local_data(self, handle: str) -> int:
        """Delete local data and backup files for a handle. Returns number of files deleted."""
        try:
            if not handle:
                return 0
            safe = handle.replace(".", "_")
            deleted = 0
            # Delete JSON
            json_path = self.json_dir / f"{safe}.json"
            if json_path.exists():
                try:
                    json_path.unlink()
                    console.print(f"Deleted {json_path}")
                    deleted += 1
                except Exception as e:
                    console.print(f"Failed to delete {json_path}: {e}")
            # Delete backup files (both plain and timestamped)
            for backup_path in list(self.backups_dir.glob(f"{safe}*.car")):
                try:
                    backup_path.unlink()
                    console.print(f"Deleted {backup_path}")
                    deleted += 1
                except Exception as e:
                    console.print(f"Failed to delete {backup_path}: {e}")
            if deleted == 0:
                console.print("[dim]No data files found to delete[/dim]")
            return deleted
        except Exception as e:
            console.print(f"Error clearing local data: {e}")
            return 0

    def download_and_export_data(
        self,
        handle: str,
        limit: int = 500,
        categories: Optional[set] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        replace_existing: bool = False,
        password: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Consolidated download and export method combining authentication and data export.

        Args:
            handle: Bluesky handle to download data for
            limit: Number of items per category to download
            categories: Set of categories to download ('posts', 'likes', 'reposts')
            date_start: Optional start date filter
            date_end: Optional end date filter
            replace_existing: Whether to replace existing data file
            password: Optional password for re-authentication

        Returns:
            Path to exported JSON file or None on failure
        """
        # Re-authenticate if password provided
        if password and not self.auth.authenticate_client(handle, password):
            console.print("Authentication failed")
            return None

        # Ensure authentication
        if not self.auth.is_authenticated():
            console.print("Authentication required for data download")
            return None

        # Export data using existing method
        return self.export_user_data(
            handle, limit, categories, date_start, date_end, replace_existing
        )

    def download_backup_and_import(
        self, handle: str, categories: Optional[set] = None, replace_mode: bool = True
    ) -> Optional[Path]:
        """
        Consolidated method to download backup file and import it to data.

        Args:
            handle: Bluesky handle to download backup for
            categories: Set of categories to process from backup
            replace_mode: If True, replace existing data; if False, merge with existing

        Returns:
            Path to imported data file or None on failure
        """
        # Download backup file
        console.print(f"Downloading backup for @{handle}...")
        backup_path = self.download_backup(handle)
        if not backup_path:
            console.print("Failed to download backup file")
            return None

        console.print("Backup file downloaded successfully.")
        console.print("Processing backup...")

        # Import backup to data
        if replace_mode:
            return self.import_backup_replace(backup_path, handle, categories)
        else:
            return self.import_backup_merge(backup_path, handle, categories)
