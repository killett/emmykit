"""`emmykit.introspection`: `show_function_source` writing to a file, and `load_ast_var`."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

from emmykit.introspection import load_ast_var, show_function_source


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


def test_load_ast_var_reads_a_literal_without_running_the_module(tmp_path: Path) -> None:
    """The literal comes back; the module's other code never runs."""
    script = tmp_path / "settings.py"
    script.write_text("raise SystemExit('ran')\nLIMITS: dict = {'a': 1}\n")

    assert load_ast_var("LIMITS", script) == {"a": 1}


def test_load_ast_var_returns_none_for_a_missing_name(tmp_path: Path) -> None:
    """A name the module doesn't assign gives None."""
    script = tmp_path / "settings.py"
    script.write_text("OTHER = 1\n")

    assert load_ast_var("LIMITS", script) is None


def test_load_ast_var_returns_none_for_an_empty_module(tmp_path: Path) -> None:
    """An empty module assigns nothing, so the answer is None, as for any missing name.

    Fails if an empty file is reported as one that couldn't be opened.
    """
    script = tmp_path / "empty.py"
    script.touch()

    assert load_ast_var("LIMITS", script) is None
