"""Unit tests for site_gpt5 web batching helpers."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Dict, List

import pytest

SITE_DIR = Path(__file__).resolve().parents[2] / "site_gpt5"
if str(SITE_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_DIR))

from types import SimpleNamespace

import web_simple  # noqa: E402


class _FakeBatchResult(SimpleNamespace):
    def __init__(self, results):
        super().__init__(results=results)


@pytest.mark.parametrize(
    "payload, expected_uris",
    [
        ([{"uri": "at://did:example/post/one"}], ["at://did:example/post/one"]),
        (
            [[{"uri": "at://did:legacy/post/two"}, {"uri": "at://did:legacy/post/three"}]],
            ["at://did:legacy/post/two", "at://did:legacy/post/three"],
        ),
    ],
)
def test_iter_batch_post_payloads_handles_various_shapes(
    payload: List[Dict[str, object]],
    expected_uris: List[str],
) -> None:
    batch_result = _FakeBatchResult(results=payload)
    seen = [post["uri"] for post in web_simple._iter_batch_post_payloads(batch_result)]
    assert seen == expected_uris


def test_iter_batch_post_payloads_ignores_non_dict_entries() -> None:
    payload = [{"uri": "at://did:one"}, ["not-a-dict"], {"not_uri": 1}]
    batch_result = _FakeBatchResult(results=payload)
    seen = list(web_simple._iter_batch_post_payloads(batch_result))
    assert seen == [{"uri": "at://did:one"}]
