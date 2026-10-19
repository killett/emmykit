"""Fixtures shared by every test module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def cache_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cache folder at a fresh temp folder, so no test writes to the real one.

    `my_atomic_write` keeps its lock files under `$XDG_CACHE_HOME/emmykit/locks`.
    """
    cache = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("XDG_CACHE_HOME", os.fspath(cache))
    return cache
