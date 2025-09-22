"""Tests for the CLI entrypoint behaviours."""

import pytest

from skymarshal import app


def test_cli_handles_broken_pipe(monkeypatch):
    """`cli` should exit cleanly when downstream pipes close early."""

    class FakeManager:
        def run(self) -> None:
            raise BrokenPipeError()

    monkeypatch.setattr(app.sys, "argv", ["skymarshal"])
    monkeypatch.setattr(app, "show_banner", lambda: None)
    monkeypatch.setattr(app, "InteractiveContentManager", lambda: FakeManager())

    with pytest.raises(SystemExit) as excinfo:
        app.cli()

    assert excinfo.value.code == 0
