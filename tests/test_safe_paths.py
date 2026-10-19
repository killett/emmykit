"""`ensure_file`: what it says about an empty file."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from emmykit.safe_paths import ensure_file


def test_empty_file_warning_names_the_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The warning reads "File is empty: <path>", with no leftover debugging marker."""
    path = tmp_path / "empty.txt"
    path.touch()
    caplog.set_level(logging.WARNING)

    assert ensure_file(path) == path

    assert [r.getMessage() for r in caplog.records] == [f"File is empty: {os.fspath(path)}"]


def test_empty_file_error_names_the_file(tmp_path: Path) -> None:
    """With raise_on_empty, the ValueError reads "File is empty: <path>"."""
    path = tmp_path / "empty.txt"
    path.touch()

    with pytest.raises(ValueError) as excinfo:
        ensure_file(path, raise_on_empty=True)

    assert str(excinfo.value) == f"File is empty: {os.fspath(path)}"
