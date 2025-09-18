"""
Skymarshal Content Deletion Operations

File Purpose: Safe content deletion workflows with multiple approval modes
Primary Functions/Classes: DeletionManager
Inputs and Outputs (I/O): Content items for deletion, AT Protocol delete operations

This module provides secure content deletion capabilities with multiple approval workflows,
progress tracking, and comprehensive safety checks for Bluesky content management.
"""

import time
from datetime import datetime
from typing import Any, List, Optional, Tuple

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule

from .auth import AuthManager
from .models import ContentItem, DeleteMode, UserSettings, console, parse_datetime


class DeletionManager:
    """Manages content deletion operations."""

    def __init__(self, auth_manager: AuthManager, settings: UserSettings):
        self.auth = auth_manager
        self.settings = settings

    def delete_records_by_uri(self, uris: List[str]) -> Tuple[int, List[str]]:
        """Delete records by their at:// URIs. Returns (deleted_count, errors)."""
        if not self.auth.ensure_authentication():
            return 0, ["Not authenticated"]

        errors: List[str] = []
        deleted = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Deleting records...", total=len(uris))

            for uri in uris:
                try:
                    parts = uri.split("/") if uri else []
                    if len(parts) >= 5 and uri.startswith("at://"):
                        did = parts[2]
                        # Fallback: replace placeholder DID with the authenticated user's DID
                        if did == "did:plc:unknown" and self.auth.current_did:
                            did = self.auth.current_did
                        collection = parts[3]
                        rkey = parts[4]
                        self.auth.client.com.atproto.repo.delete_record(
                            {"repo": did, "collection": collection, "rkey": rkey}
                        )
                        deleted += 1
                    else:
                        errors.append(f"Invalid at:// URI: {uri}")
                except Exception as e:
                    errors.append(f"Failed to delete {uri}: {e}")
                finally:
                    progress.advance(task, 1)

        return deleted, errors

    def delete_content_with_progress(self, items: List[ContentItem]) -> int:
        """Delete content with progress tracking."""
        if not self.auth.ensure_authentication():
            console.print("Authentication required for deletion")
            return 0

        deleted_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:

            task = progress.add_task("Deleting content...", total=len(items))

            for item in items:
                try:
                    parts = item.uri.split("/") if item.uri else []
                    if len(parts) >= 5 and item.uri.startswith("at://"):
                        did = parts[2]
                        # Fallback: replace placeholder DID with the authenticated user's DID
                        if did == "did:plc:unknown" and self.auth.current_did:
                            did = self.auth.current_did
                        collection = parts[3]
                        rkey = parts[4]

                        if collection not in (
                            "app.bsky.feed.post",
                            "app.bsky.feed.like",
                            "app.bsky.feed.repost",
                        ):
                            console.print(
                                f"Unsupported collection for deletion: {collection}"
                            )
                        else:
                            try:
                                self.auth.client.com.atproto.repo.delete_record(
                                    {
                                        "repo": did,
                                        "collection": collection,
                                        "rkey": rkey,
                                    }
                                )
                                deleted_count += 1
                            except Exception:
                                # Fallback: for likes/reposts, locate record by subject URI if rkey is wrong
                                if collection in (
                                    "app.bsky.feed.like",
                                    "app.bsky.feed.repost",
                                ):
                                    subject_uri = (item.raw_data or {}).get(
                                        "subject_uri"
                                    )
                                    if subject_uri and self._delete_by_subject(
                                        collection, subject_uri
                                    ):
                                        deleted_count += 1
                                    else:
                                        raise
                                else:
                                    raise
                    else:
                        console.print(f"Invalid at:// URI: {item.uri}")

                    progress.update(task, advance=1)
                    time.sleep(0.1)

                except Exception as e:
                    console.print(f"Failed to delete {item.uri}: {e}")
                    progress.update(task, advance=1)

        return deleted_count

    def _delete_by_subject(self, collection: str, subject_uri: str) -> bool:
        """Find and delete a like/repost by its subject URI in the current user's repo."""
        try:
            if not self.auth.ensure_authentication():
                return False
            did = self.auth.current_did
            if not did:
                return False
            cursor = None
            per_page = 100
            while True:
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": collection,
                        "cursor": cursor,
                        "limit": per_page,
                    }
                )
                records = getattr(resp, "records", []) or []
                if not records:
                    break
                for rec in records:
                    value = getattr(rec, "value", None)
                    if value is None and isinstance(rec, dict):
                        value = rec.get("value")
                    subj = None
                    if value is not None:
                        subj_obj = (
                            getattr(value, "subject", None)
                            if not isinstance(value, dict)
                            else value.get("subject")
                        )
                        if subj_obj is not None:
                            subj = (
                                getattr(subj_obj, "uri", None)
                                if not isinstance(subj_obj, dict)
                                else subj_obj.get("uri")
                            )
                    if subj == subject_uri:
                        rkey = getattr(rec, "uri", "///").split("/")[-1]
                        self.auth.client.com.atproto.repo.delete_record(
                            {
                                "repo": did,
                                "collection": collection,
                                "rkey": rkey,
                            }
                        )
                        return True
                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break
        except Exception:
            return False
        return False

    def delete_all_at_once(self, items: List[ContentItem], display_func):
        """Delete all items with single confirmation."""
        console.print()
        console.print("Review ALL items to be deleted:")
        display_func(items, limit=len(items))
        console.print()

        console.print(
            Panel(
                f"WARNING: You are about to permanently delete [bold red]{len(items)}[/] items from Bluesky!\n\n"
                f"This action cannot be undone and will make real API calls.",
                title="FINAL WARNING",
                border_style="bright_red",
            )
        )
        console.print()

        if not Confirm.ask(
            f"[bold white]Are you absolutely sure you want to delete {len(items)} items?[/]"
        ):
            console.print("[yellow]Deletion cancelled[/]")
            return

        if not Confirm.ask("[bold white]Last chance - really delete everything?[/]"):
            console.print("[yellow]Deletion cancelled[/]")
            return

        deleted_count = self.delete_content_with_progress(items)
        console.print()
        console.print(f"Successfully deleted [bold green]{deleted_count}[/] items")

    def delete_individual_approval(self, items: List[ContentItem], display_single_func):
        """Delete with individual approval for each item."""
        console.print()
        console.print("Individual Review Mode")
        console.print("Review each item and decide whether to delete it")
        console.print()

        to_delete = []

        for i, item in enumerate(items, 1):
            console.print(Rule(f"Item {i} of {len(items)}", style="dim"))
            display_single_func(item)

            console.print(f"  [d] Delete this item")
            console.print(f"  (s) Skip this item")
            console.print(f"  (q) Quit review")
            console.print()

            choice = Prompt.ask(
                "[bold white]Action[/]",
                choices=["d", "s", "q"],
                default="s",
                show_choices=False,
            )

            if choice == "d":
                to_delete.append(item)
                console.print("Marked for deletion")
            elif choice == "s":
                console.print("Skipped")
            elif choice == "q":
                break

            console.print()

        if to_delete:
            console.print(f"{len(to_delete)} items marked for deletion")
            if Confirm.ask("Proceed with deletion?"):
                deleted_count = self.delete_content_with_progress(to_delete)
                console.print(f"Deleted {deleted_count} items")
            else:
                console.print("Deletion cancelled")
        else:
            console.print("No items selected for deletion")

    def delete_batch_approval(self, items: List[ContentItem], display_func):
        """Delete in batches with approval."""
        batch_size = IntPrompt.ask("[bold white]Batch size[/]", default=10)
        batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

        console.print(
            f"Will process {len(batches)} batches of ~{batch_size} items each"
        )
        console.print()

        total_deleted = 0

        for i, batch in enumerate(batches, 1):
            console.print(Rule(f"Batch {i} of {len(batches)}", style="yellow"))
            console.print()

            console.print(f"Batch contains {len(batch)} items:")
            display_func(batch, limit=len(batch))
            console.print()

            console.print(f"  [d] Delete this batch")
            console.print(f"  (s) Skip this batch")
            console.print(f"  (q) Quit batch processing")

            choice = Prompt.ask(
                "[bold white]Action for this batch[/]",
                choices=["d", "s", "q"],
                default="s",
            )

            if choice == "d":
                deleted_count = self.delete_content_with_progress(batch)
                total_deleted += deleted_count
                console.print(f"Deleted {deleted_count} items from batch {i}")
            elif choice == "s":
                console.print(f"Skipped batch {i}")
            elif choice == "q":
                break

            console.print()

        console.print(f"Total deleted: {total_deleted} items")

    def bulk_remove_by_collection(
        self,
        collection: str,
        subject_contains: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ) -> Tuple[int, int]:
        """Delete records in a collection matching simple filters."""
        dt_after = parse_datetime(after)
        dt_before = parse_datetime(before)

        matched = 0
        deleted = 0

        for rec in self._iterate_repo_records(collection, max_items=limit):
            value = getattr(rec, "value", None)
            created = getattr(value, "created_at", None) if value is not None else None
            if not created and isinstance(value, dict):
                created = value.get("createdAt")

            if created and (dt_after or dt_before):
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    created_dt = None
                if dt_after and created_dt and created_dt < dt_after:
                    continue
                if dt_before and created_dt and created_dt > dt_before:
                    continue

            if subject_contains and collection in (
                "app.bsky.feed.like",
                "app.bsky.feed.repost",
            ):
                subj = None
                if value is not None:
                    subj_obj = getattr(value, "subject", None)
                    if subj_obj is None and isinstance(value, dict):
                        subj_obj = value.get("subject")
                    if subj_obj is not None:
                        subj = (
                            getattr(subj_obj, "uri", None)
                            if not isinstance(subj_obj, dict)
                            else subj_obj.get("uri")
                        )
                if not subj or subject_contains.lower() not in subj.lower():
                    continue

            matched += 1
            if not dry_run:
                try:
                    # Fallback: replace placeholder DID with the authenticated user's DID for repo param
                    repo_did = getattr(rec, "uri", "at://").split("/")[2]
                    if repo_did == "did:plc:unknown" and self.auth.current_did:
                        repo_did = self.auth.current_did
                    self.auth.client.com.atproto.repo.delete_record(
                        {
                            "repo": repo_did,
                            "collection": collection,
                            "rkey": getattr(rec, "uri", "///").split("/")[-1],
                        }
                    )
                    deleted += 1
                except Exception:
                    pass

        return deleted, matched

    def _iterate_repo_records(self, collection: str, max_items: Optional[int] = None):
        """Yield records from current user's repo for a collection using cursors."""
        if not self.auth.ensure_authentication():
            return

        did = self.auth.current_did
        if not did:
            try:
                did = getattr(getattr(self.auth.client, "me", None), "did", None)
            except Exception:
                did = None

        if not did:
            console.print(
                "[yellow]Could not determine current DID; please enter your DID[/yellow]"
            )
            did = Prompt.ask("DID (did:plc:...)")

        if not did:
            raise RuntimeError("Could not determine current DID")

        cursor: Optional[str] = None
        per_page = 100
        order = self.settings.fetch_order

        if order == "oldest":
            all_recs: List[Any] = []
            while True:
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": collection,
                        "cursor": cursor,
                        "limit": per_page,
                    }
                )
                records = getattr(resp, "records", []) or []
                if not records:
                    break
                all_recs.extend(records)
                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break

            all_recs.reverse()
            if max_items is not None:
                all_recs = all_recs[:max_items]
            for rec in all_recs:
                yield rec
        else:
            fetched = 0
            while True:
                if max_items is not None and fetched >= max_items:
                    break
                limit = (
                    per_page
                    if max_items is None
                    else min(per_page, max_items - fetched)
                )
                resp = self.auth.client.com.atproto.repo.list_records(
                    {
                        "repo": did,
                        "collection": collection,
                        "cursor": cursor,
                        "limit": limit,
                    }
                )
                records = getattr(resp, "records", []) or []
                if not records:
                    break
                for rec in records:
                    yield rec
                    fetched += 1
                    if max_items is not None and fetched >= max_items:
                        break
                cursor = getattr(resp, "cursor", None)
                if not cursor:
                    break
