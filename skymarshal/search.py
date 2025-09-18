"""
Skymarshal Content Search and Filtering Engine

File Purpose: Advanced content search, filtering, and analysis operations
Primary Functions/Classes: SearchManager
Inputs and Outputs (I/O): Content items, search filters, filtered results

This module provides sophisticated search and filtering capabilities for Bluesky content,
including keyword matching, engagement-based filtering, date ranges, and content type filtering.
"""

import re
from datetime import datetime
from typing import List, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule

from .auth import AuthManager
from .models import (
    ContentItem,
    ContentType,
    SearchFilters,
    UserSettings,
    calculate_engagement_score,
    console,
    parse_datetime,
)


class SearchManager:
    """Manages content search and filtering operations."""

    def __init__(self, auth_manager: AuthManager, settings: UserSettings):
        self.auth = auth_manager
        self.settings = settings

    def build_search_filters(self, ui_manager=None) -> Optional[SearchFilters]:
        """Interactive filter builder."""
        console.print(Rule("[bright_cyan]Build Search Filters[/]", style="bright_cyan"))

        filters = SearchFilters()

        # Use the UI manager if available for consistent prompts
        if ui_manager:
            content_type_choices = {
                "1": ("all", "All content"),
                "2": ("posts", "Original posts only"),
                "3": ("replies", "Replies/comments only"),
                "4": ("reposts", "Reposts only"),
                "5": ("likes", "Likes only"),
            }

            console.print("[bright_cyan]Content Type Selection[/]")
            content_type_value, action = ui_manager.prompt_with_choices(
                "Select content type",
                choices=content_type_choices,
                default="1",
                context="content_type",
            )
            if action == "back":
                return None
            filters.content_type = ContentType(content_type_value)
        else:
            # Fallback to old method if no UI manager
            content_types = {
                "1": ("all", "All content"),
                "2": ("posts", "Original posts only"),
                "3": ("replies", "Replies/comments only"),
                "4": ("reposts", "Reposts only"),
                "5": ("likes", "Likes only"),
            }

            console.print(
                Rule("[bright_cyan]Content Type Selection[/]", style="bright_cyan")
            )
            console.print()
            for key, (_, desc) in content_types.items():
                console.print(f"  [bold white]\\[{key}][/] {desc}")

            type_choice = Prompt.ask(
                "[bold white]Select content type[/]",
                choices=list(content_types.keys()),
                default="1",
                show_choices=False,
            )
            content_type_value, _ = content_types[type_choice]
            filters.content_type = ContentType(content_type_value)

        console.print()

        if ui_manager:
            add_keywords, keyword_action = ui_manager.prompt_confirm(
                "Add keyword filters?", default=False, context="add_keywords"
            )
            if keyword_action == "back":
                return None
            if add_keywords:
                keywords_input, input_action = ui_manager.prompt_text(
                    "Enter keywords (comma separated):", default="", context="keywords"
                )
                if input_action == "back":
                    return None
                if keywords_input:
                    filters.keywords = [
                        k.strip() for k in keywords_input.split(",") if k.strip()
                    ]
        else:
            if Confirm.ask("[bold white]Add keyword filters?[/]", default=False):
                keywords_input = Prompt.ask(
                    "[bold white]Enter keywords (comma separated):[/] ", default=""
                )
                if keywords_input:
                    filters.keywords = [
                        k.strip() for k in keywords_input.split(",") if k.strip()
                    ]

        console.print()

        if ui_manager:
            add_engagement, engagement_action = ui_manager.prompt_confirm(
                "Add engagement filters?", default=False, context="add_engagement"
            )
            if engagement_action == "back":
                return None
            if add_engagement:
                console.print()
                console.print(
                    Rule("[bright_yellow]Engagement Filters[/]", style="bright_yellow")
                )

                filter_choices = {
                    "1": ("presets", "Quick presets"),
                    "2": ("custom", "Custom thresholds"),
                }

                filter_choice, filter_action = ui_manager.prompt_with_choices(
                    "Choose filter type",
                    choices=filter_choices,
                    default="1",
                    context="filter_type",
                )
                if filter_action == "back":
                    return None

                if filter_choice == "presets":
                    result = self._apply_engagement_presets(filters, ui_manager)
                    if result is None:  # User went back
                        return None
                else:
                    result = self._apply_custom_engagement_filters(filters, ui_manager)
                    if result is None:  # User went back
                        return None
        else:
            if Confirm.ask("[bold white]Add engagement filters?[/]", default=False):
                console.print()
                console.print(Rule("💫 Engagement Filters", style="bright_yellow"))
                console.print()

                filter_options = {"1": "Quick presets", "2": "Custom thresholds"}

                console.print("Choose filter type:")
                for key, desc in filter_options.items():
                    console.print(f"  [{key}] {desc}")

                filter_choice = Prompt.ask(
                    "Select filter option", choices=list(filter_options.keys())
                )

                if filter_choice == "1":
                    self._apply_engagement_presets(filters)
                else:
                    self._apply_custom_engagement_filters(filters)

        # No pause needed - proceed directly to search

        return filters

    def search_content_with_filters(
        self, content_items: List[ContentItem], filters: SearchFilters
    ) -> List[ContentItem]:
        """Search content using filters."""
        filtered_items = content_items.copy()

        # Determine whether to show progress based on dataset size
        show_progress = len(filtered_items) >= 1000

        sd = parse_datetime(getattr(filters, "start_date", None))
        ed = parse_datetime(getattr(filters, "end_date", None))
        use_subject = self.settings.use_subject_engagement_for_reposts

        def counts_for(it: ContentItem):
            if it.content_type == "repost" and use_subject:
                rd = it.raw_data or {}
                l = int(rd.get("subject_like_count", 0) or 0)
                r = int(rd.get("subject_repost_count", 0) or 0)
                rp = int(rd.get("subject_reply_count", 0) or 0)
                return l, r, rp
            else:
                return (
                    int(it.like_count or 0),
                    int(it.repost_count or 0),
                    int(it.reply_count or 0),
                )

        def passes(it: ContentItem) -> bool:
            l, r, rp = counts_for(it)
            eng = calculate_engagement_score(l, r, rp)

            if sd or ed:
                dt = parse_datetime(it.created_at)
                if dt is None:
                    return False
                if sd and dt < sd:
                    return False
                if ed and dt > ed:
                    return False

            return (
                filters.min_engagement <= eng <= filters.max_engagement
                and filters.min_likes <= l <= filters.max_likes
                and filters.min_reposts <= r <= filters.max_reposts
                and filters.min_replies <= rp <= filters.max_replies
            )

        # Keyword regex precompute
        regex = None
        if filters.keywords:
            keyword_pattern = "|".join(
                re.escape(keyword) for keyword in filters.keywords
            )
            regex = re.compile(keyword_pattern, re.IGNORECASE)

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
                console=console,
            ) as progress:
                # Step 1: Keyword filter (optional)
                if regex is not None:
                    task_kw = progress.add_task(
                        f"Applying keyword filter 0/{len(filtered_items)}",
                        total=len(filtered_items),
                    )
                    tmp = []
                    for it in filtered_items:
                        if it.text and regex.search(it.text):
                            tmp.append(it)
                        progress.advance(task_kw, 1)
                    filtered_items = tmp

                # Step 2: Criteria pass
                task_criteria = progress.add_task(
                    f"Evaluating filters 0/{len(filtered_items)}",
                    total=max(1, len(filtered_items)),
                )
                tmp2 = []
                for it in filtered_items:
                    if passes(it):
                        tmp2.append(it)
                    progress.advance(task_criteria, 1)
                filtered_items = tmp2
        else:
            if regex is not None:
                filtered_items = [
                    it for it in filtered_items if it.text and regex.search(it.text)
                ]
            filtered_items = [it for it in filtered_items if passes(it)]

        if filters.content_type != ContentType.ALL:

            def _matches_type(it: ContentItem) -> bool:
                if filters.content_type in (ContentType.REPLIES, ContentType.COMMENTS):
                    return it.content_type == "reply"
                if filters.content_type == ContentType.POSTS:
                    return it.content_type == "post"
                if filters.content_type == ContentType.REPOSTS:
                    return it.content_type == "repost"
                if filters.content_type == ContentType.LIKES:
                    return it.content_type == "like"
                return True

            filtered_items = [it for it in filtered_items if _matches_type(it)]

        subj_sub = getattr(filters, "subject_contains", None)
        if subj_sub:
            sub_lower = subj_sub.lower()

            def _subj_match(it: ContentItem) -> bool:
                if it.content_type not in ("like", "repost"):
                    return True
                subj = (it.raw_data or {}).get("subject_uri")
                return bool(subj and sub_lower in subj.lower())

            filtered_items = [it for it in filtered_items if _subj_match(it)]

        subj_handle_sub = getattr(filters, "subject_handle_contains", None)
        if subj_handle_sub:
            filtered_items = self._filter_by_subject_handle(
                filtered_items, subj_handle_sub
            )

        order = self.settings.fetch_order

        def sort_dt(it: ContentItem):
            s = it.created_at
            try:
                return (
                    datetime.fromisoformat(s.replace("Z", "+00:00"))
                    if isinstance(s, str)
                    else datetime.min
                )
            except Exception:
                return datetime.min

        filtered_items.sort(key=sort_dt, reverse=(order == "newest"))

        return filtered_items

    def sort_results(
        self, filtered_items: List[ContentItem], sort_mode: str
    ) -> List[ContentItem]:
        """Sort search results by specified criteria."""

        def key_dt(it: ContentItem):
            return parse_datetime(it.created_at, datetime.min)

        def key_eng(it: ContentItem):
            return (
                int(it.like_count or 0)
                + 2 * int(it.repost_count or 0)
                + 2.5 * int(it.reply_count or 0)
            )

        def key_likes(it: ContentItem):
            return int(it.like_count or 0)

        def key_replies(it: ContentItem):
            return int(it.reply_count or 0)

        def key_reposts(it: ContentItem):
            return int(it.repost_count or 0)

        if sort_mode == "newest":
            filtered_items.sort(key=key_dt, reverse=True)
        elif sort_mode == "oldest":
            filtered_items.sort(key=key_dt)
        elif sort_mode == "eng_desc":
            filtered_items.sort(key=key_eng, reverse=True)
        elif sort_mode == "eng_asc":
            filtered_items.sort(key=key_eng)
        elif sort_mode == "likes_desc":
            filtered_items.sort(key=key_likes, reverse=True)
        elif sort_mode == "replies_desc":
            filtered_items.sort(key=key_replies, reverse=True)
        elif sort_mode == "reposts_desc":
            filtered_items.sort(key=key_reposts, reverse=True)

        return filtered_items

    def get_sort_options(self) -> dict:
        """Get available sorting options."""
        return {
            "1": ("Newest first", "newest"),
            "2": ("Oldest first", "oldest"),
            "3": ("Most engagement", "eng_desc"),
            "4": ("Least engagement", "eng_asc"),
            "5": ("Most likes", "likes_desc"),
            "6": ("Most replies", "replies_desc"),
            "7": ("Most reposts", "reposts_desc"),
        }

    def _apply_engagement_presets(self, filters: SearchFilters, ui_manager=None):
        """Apply preset engagement filters based on user's average likes.

        Categories:
        1) Dead Thread: 0 likes
        2) Bomber: <= 0.5 × avg likes
        3) Mid: around avg likes (0.5× to 1.5×)
        4) Banger: >= 2 × avg likes
        5) Viral: >= min(10 × avg likes, 500) likes
        """
        avg_likes = getattr(self.settings, "avg_likes_per_post", 0.0) or 0.0
        # Clamp thresholds when average is zero to avoid classifying everything as a banger
        half = int(max(0.0, avg_likes * 0.5))
        one_half = int(max(1.0, avg_likes * 1.5))
        double = int(max(1.0, avg_likes * 2.0))

        # Viral threshold: use relative (10x average) OR absolute (500+ likes) for flexibility
        viral_relative = int(max(10.0, avg_likes * 10.0))
        viral_threshold = max(
            viral_relative, 2000
        )  # Ensure viral is always 2000+ minimum

        preset_choices = {
            "1": ("dead", f"Dead Threads (0 likes, 0 engagement)"),
            "2": ("bombers", f"Bombers (≤ {half} likes)"),
            "3": ("mid", f"Mid ({half}-{one_half} likes)"),
            "4": ("bangers", f"Bangers (≥ {double} likes)"),
            "5": ("viral", f"Viral (≥ {viral_threshold} likes)"),
        }

        console.print()
        console.print("[bright_yellow]Engagement Presets:[/]")

        if ui_manager:
            preset_choice, preset_action = ui_manager.prompt_with_choices(
                "Select preset",
                choices=preset_choices,
                default="1",
                context="engagement_preset",
            )
            if preset_action == "back":
                return None
        else:
            for key, (_, desc) in preset_choices.items():
                console.print(f"  [bold white]\\[{key}][/] {desc}")
            preset_choice = Prompt.ask(
                "[bold white]Select preset[/]",
                choices=list(preset_choices.keys()),
                default="1",
                show_choices=False,
            )

        # Apply the selected preset
        preset_values = {
            "dead": {"max_likes": 0, "max_engagement": 0},
            "bombers": {"min_likes": 0, "max_likes": max(0, half)},
            "mid": {"min_likes": max(0, half), "max_likes": max(1, one_half)},
            "bangers": {"min_likes": max(1, double)},
            "viral": {"min_likes": viral_threshold},
        }

        values = preset_values.get(preset_choice, {})
        for key, value in values.items():
            setattr(filters, key, value)
        return filters

    def _apply_custom_engagement_filters(self, filters: SearchFilters, ui_manager=None):
        """Apply custom engagement filters."""
        console.print()
        console.print(
            Rule(
                "[bright_magenta]Custom Engagement Thresholds[/]",
                style="bright_magenta",
            )
        )
        console.print("[dim](Leave blank to skip any filter)[/]")
        console.print()

        if ui_manager:
            min_likes, action = ui_manager.prompt_integer(
                "Minimum likes:", default=0, min_val=0, context="min_likes"
            )
            if action == "back":
                return None
            max_likes, action = ui_manager.prompt_integer(
                "Maximum likes:", default=999999, min_val=0, context="max_likes"
            )
            if action == "back":
                return None
            filters.min_likes = min_likes
            filters.max_likes = max_likes

            min_reposts, action = ui_manager.prompt_integer(
                "Minimum reposts:", default=0, min_val=0, context="min_reposts"
            )
            if action == "back":
                return None
            max_reposts, action = ui_manager.prompt_integer(
                "Maximum reposts:", default=999999, min_val=0, context="max_reposts"
            )
            if action == "back":
                return None
            filters.min_reposts = min_reposts
            filters.max_reposts = max_reposts

            min_replies, action = ui_manager.prompt_integer(
                "Minimum replies:", default=0, min_val=0, context="min_replies"
            )
            if action == "back":
                return None
            max_replies, action = ui_manager.prompt_integer(
                "Maximum replies:", default=999999, min_val=0, context="max_replies"
            )
            if action == "back":
                return None
            filters.min_replies = min_replies
            filters.max_replies = max_replies

            add_date, action = ui_manager.prompt_confirm(
                "Add date range filters?", default=False, context="add_date"
            )
            if action == "back":
                return None
            if add_date:
                console.print("[bright_cyan]Date Range (YYYY-MM-DD or ISO8601)[/]")
                sd, action = ui_manager.prompt_text(
                    "Start date:", default="", context="start_date"
                )
                if action == "back":
                    return None
                ed, action = ui_manager.prompt_text(
                    "End date:", default="", context="end_date"
                )
                if action == "back":
                    return None
                filters.start_date = sd or None
                filters.end_date = ed or None

            add_subj_uri, action = ui_manager.prompt_confirm(
                "Filter likes/reposts by subject URI contains?",
                default=False,
                context="add_subj_uri",
            )
            if action == "back":
                return None
            if add_subj_uri:
                subj, action = ui_manager.prompt_text(
                    "Enter subject URI substring:", default="", context="subj_uri"
                )
                if action == "back":
                    return None
                filters.subject_contains = subj or None

            add_subj_handle, action = ui_manager.prompt_confirm(
                "Filter likes/reposts by subject HANDLE contains?",
                default=False,
                context="add_subj_handle",
            )
            if action == "back":
                return None
            if add_subj_handle:
                subjh, action = ui_manager.prompt_text(
                    "Enter subject handle substring:", default="", context="subj_handle"
                )
                if action == "back":
                    return None
                filters.subject_handle_contains = subjh or None
        else:
            # Fallback to old prompts
            min_likes = Prompt.ask("[bold white]Minimum likes:[/] ", default="0")
            max_likes = Prompt.ask("[bold white]Maximum likes:[/] ", default="999999")
            filters.min_likes = int(min_likes) if min_likes else 0
            filters.max_likes = int(max_likes) if max_likes else 999999

            min_reposts = Prompt.ask("[bold white]Minimum reposts:[/] ", default="0")
            max_reposts = Prompt.ask(
                "[bold white]Maximum reposts:[/] ", default="999999"
            )
            filters.min_reposts = int(min_reposts) if min_reposts else 0
            filters.max_reposts = int(max_reposts) if max_reposts else 999999

            min_replies = Prompt.ask("[bold white]Minimum replies:[/] ", default="0")
            max_replies = Prompt.ask(
                "[bold white]Maximum replies:[/] ", default="999999"
            )
            filters.min_replies = int(min_replies) if min_replies else 0
            filters.max_replies = int(max_replies) if max_replies else 999999

            if Confirm.ask("[bold white]Add date range filters?[/]", default=False):
                console.print("[bright_cyan]Date Range (YYYY-MM-DD or ISO8601)[/]")
                sd = Prompt.ask("[bold white]Start date:[/] ", default="")
                ed = Prompt.ask("[bold white]End date:[/] ", default="")
                filters.start_date = sd or None
                filters.end_date = ed or None

            if Confirm.ask(
                "[bold white]Filter likes/reposts by subject URI contains?[/]",
                default=False,
            ):
                subj = Prompt.ask(
                    "[bold white]Enter subject URI substring:[/] ", default=""
                )
                filters.subject_contains = subj or None

            if Confirm.ask(
                "[bold white]Filter likes/reposts by subject HANDLE contains?[/]",
                default=False,
            ):
                subjh = Prompt.ask(
                    "[bold white]Enter subject handle substring:[/] ", default=""
                )
                filters.subject_handle_contains = subjh or None

        return filters

    def _filter_by_subject_handle(
        self, filtered_items: List[ContentItem], subj_handle_sub: str
    ) -> List[ContentItem]:
        """Filter items by subject handle containing substring."""
        need = [it for it in filtered_items if it.content_type in ("like", "repost")]
        dids = set()

        for it in need:
            subj = (it.raw_data or {}).get("subject_uri")
            if subj and subj.startswith("at://"):
                parts = subj.split("/")
                if len(parts) >= 3:
                    dids.add(parts[2])

        did_to_handle = {}
        if dids and self.auth.ensure_authentication():
            try:
                actors = list(dids)
                for i in range(0, len(actors), 25):
                    batch = actors[i : i + 25]
                    resp = self.auth.client.get_profiles(actors=batch)
                    for p in getattr(resp, "profiles", []) or []:
                        did_to_handle[getattr(p, "did", "")] = getattr(p, "handle", "")
            except Exception:
                pass

        subh_lower = subj_handle_sub.lower()

        def _subj_handle_match(it: ContentItem) -> bool:
            if it.content_type not in ("like", "repost"):
                return True
            subj = (it.raw_data or {}).get("subject_uri")
            if not subj or not subj.startswith("at://"):
                return False
            did = subj.split("/")[2]
            handle = did_to_handle.get(did, "")
            return bool(handle and subh_lower in handle.lower())

        return [it for it in filtered_items if _subj_handle_match(it)]
