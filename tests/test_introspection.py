"""`show_function_source` writing a function's source to a file."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

from emmykit.introspection import show_function_source


def sample(x: int) -> int:
    """Return x doubled."""
    return 2 * x


def test_writes_then_appends_with_a_note_each_time(tmp_path: Path) -> None:
    """The first write creates the file, the second appends; each copy gets a one-line note."""
    path = tmp_path / "out.py"
    source = inspect.getsource(sample)

    show_function_source(sample, output=path)
    show_function_source(sample, output=os.fspath(path))

    assert path.read_text() == (
        f"# Creating new file: {os.fspath(path)}\n{source}"
        f"# Appending to existing file: {os.fspath(path)}\n{source}"
    )
