#!/usr/bin/env python3
"""
Simple Flask site: login → fetch last 50 posts → hydrate likes/reposts/quotes/replies
with live progress (Server-Sent Events) and final summary.

Run:
  python web_simple.py  # defaults to port 5006

Dependencies:
  pip install atproto requests flask
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, Response, session

try:
    from atproto import Client
except Exception:  # pragma: no cover
    Client = None  # type: ignore

from improved_hydration import BlueskyEngagementHydrator

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.secret_key = secrets.token_hex(32)

# In-memory auth store by session id
_auth: Dict[str, Dict[str, Any]] = {}


def _normalize_handle(handle: str) -> str:
    h = handle.lstrip("@").strip()
    if "." not in h:
        h = f"{h}.bsky.social"
    return h


def _list_last_posts(client: Client, did: str, limit: int = 50) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    per_page = 100
    while len(posts) < limit:
        resp = client.com.atproto.repo.list_records(
            {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "limit": min(per_page, limit - len(posts)),
                "cursor": cursor,
            }
        )
        records = getattr(resp, "records", []) or []
        if not records:
            break
        for rec in records:
            uri = getattr(rec, "uri", None)
            value = getattr(rec, "value", None) or {}
            # Skip replies
            is_reply = False
            if hasattr(value, "reply"):
                is_reply = bool(getattr(value, "reply") or None)
            elif isinstance(value, dict):
                is_reply = value.get("reply") is not None
            if is_reply:
                continue
            text = getattr(value, "text", None) if hasattr(value, "text") else value.get("text") if isinstance(value, dict) else None
            created_at = (
                getattr(value, "created_at", None)
                if hasattr(value, "created_at")
                else value.get("createdAt") if isinstance(value, dict) else None
            )
            if uri:
                posts.append({"uri": uri, "text": text, "created_at": created_at})
            if len(posts) >= limit:
                break
        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break
    return posts


@app.route("/")
def index():
    info = None
    sid = session.get("sid")
    if sid and sid in _auth:
        info = {
            "handle": _auth[sid]["handle"],
            "display_name": _auth[sid].get("display_name"),
        }
    return render_template("simple.html", info=info)


@app.route("/login", methods=["POST"])  # JSON: {handle, password}
def login():
    try:
        data = request.get_json(force=True)
        handle = _normalize_handle(data.get("handle", ""))
        password = data.get("password", "")
        if not handle or not password:
            return jsonify({"success": False, "error": "Handle and password required"}), 400
        if Client is None:
            return jsonify({"success": False, "error": "Missing atproto dependency"}), 500
        client = Client()
        client.login(handle, password)
        prof = client.get_profile(handle)
        did = getattr(prof, "did", None)
        display_name = getattr(prof, "display_name", None) or getattr(prof, "displayName", None) or handle
        sid = secrets.token_hex(16)
        session["sid"] = sid
        session.modified = True
        _auth[sid] = {"client": client, "handle": handle, "did": did, "display_name": display_name}
        return jsonify({"success": True, "handle": handle, "display_name": display_name})
    except Exception as e:  # pragma: no cover
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/hydrate-stream")
def hydrate_stream():
    sid = session.get("sid")
    if not sid or sid not in _auth:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    client: Client = _auth[sid]["client"]
    handle: str = _auth[sid]["handle"]
    did: str = _auth[sid]["did"]
    display_name: str = _auth[sid]["display_name"]

    def send(event: Dict[str, Any]):
        return f"data: {json.dumps(event)}\n\n"

    def generate():
        try:
            yield send({"stage": "start", "message": f"Hello {display_name} (@{handle})"})
            yield send({"stage": "listing", "message": "Listing last 50 posts..."})
            posts = _list_last_posts(client, did, limit=50)
            yield send({"stage": "listed", "count": len(posts)})

            hydrator = BlueskyEngagementHydrator(client=None)  # Use public AppView for edges
            total = len(posts)
            hydrated = []
            totals = {"likes": 0, "reposts": 0, "replies": 0, "quotes": 0}

            for i, p in enumerate(posts, 1):
                uri = p["uri"]
                yield send({"stage": "hydrating", "index": i, "total": total, "uri": uri})
                pe = hydrator.get_detailed_engagement(uri)
                hydrated.append({
                    "uri": uri,
                    "text": p.get("text"),
                    "created_at": p.get("created_at"),
                    "like_count": pe.like_count,
                    "repost_count": pe.repost_count,
                    "reply_count": pe.reply_count,
                    "quote_count": pe.quote_count,
                })
                totals["likes"] += pe.like_count
                totals["reposts"] += pe.repost_count
                totals["replies"] += pe.reply_count
                totals["quotes"] += pe.quote_count
                # gentle pacing to avoid rate peaks
                time.sleep(0.2)

            # Save JSON file under site_gpt5/tmp
            out_dir = Path(__file__).parent / "tmp"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = out_dir / f"hydrated_{handle.replace('.', '_')}_{ts}.json"
            with open(out_path, "w") as f:
                json.dump({
                    "handle": handle,
                    "display_name": display_name,
                    "did": did,
                    "exported_at": datetime.now().isoformat(),
                    "count": len(hydrated),
                    "posts": hydrated,
                }, f, indent=2)

            yield send({
                "stage": "done",
                "summary": {
                    "username": display_name,
                    "handle": handle,
                    "posts": len(hydrated),
                    "likes": totals["likes"],
                    "comments": totals["replies"],
                    "reposts": totals["reposts"],
                    "quotes": totals["quotes"],
                    "json_path": str(out_path),
                },
            })
        except Exception as e:  # pragma: no cover
            yield send({"stage": "error", "error": str(e)})

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int((Path(__file__).parent / ".env.port").read_text().strip()) if (Path(__file__).parent / ".env.port").exists() else 5006
    app.run(host="0.0.0.0", port=port, debug=True)
