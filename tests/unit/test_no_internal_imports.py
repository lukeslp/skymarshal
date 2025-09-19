import importlib
import pytest


def test_importing_loners_internal_is_disallowed():
    with pytest.raises(ImportError):
        importlib.import_module("loners.internal")

