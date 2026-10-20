"""`emmykit.introspection`: `show_function_source` writing to a file, `load_ast_var` and `compile_code`."""

from __future__ import annotations

import errno
import inspect
import logging
import os
from pathlib import Path

import pytest

from emmykit.introspection import compile_code, load_ast_var, show_function_source


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


# --- compile_code: source or path --------------------------------------------

def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the messages logged at ERROR level."""
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


@pytest.mark.parametrize("given", ["missing.py", os.path.join("sub", "missing"), Path("missing.py")],
                         ids=["ends-in-py", "has-separator", "pathlike"])
def test_missing_path_raises_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str | Path
) -> None:
    """A path that doesn't exist is an error, not its own text compiled (`missing.py` is valid Python)."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError) as excinfo:
        compile_code(given)

    assert excinfo.value.errno == errno.ENOENT
    assert excinfo.value.filename == os.fspath(tmp_path / given)


@pytest.mark.parametrize(
    ("source", "expected"),
    [("x = 1", True), ("x = (", False), ("x = 1/2\ny = x\n", True), ("x = 1/2\ny = (\n", False)],
    ids=["one-line-ok", "one-line-bad", "multi-line-with-slash-ok", "multi-line-with-slash-bad"],
)
def test_source_text_is_compiled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, expected: bool
) -> None:
    """A one-line string with no `.py` or separator, or any multi-line string, is source."""
    monkeypatch.chdir(tmp_path)

    assert compile_code(source) is expected


def test_force_source_compiles_a_path_like_string(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """force_source=True compiles `x = 1/2` as code, although the `/` makes it look like a path."""
    monkeypatch.chdir(tmp_path)

    assert compile_code("x = 1/2", force_source=True) is True
    assert compile_code("x = 1/", force_source=True) is False


@pytest.mark.parametrize("as_str", [True, False], ids=["str", "pathlike"])
def test_existing_file_is_read_and_compiled(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, as_str: bool
) -> None:
    """A good file compiles; a file with a syntax error is False with the error naming the file."""
    good, bad = tmp_path / "good.py", tmp_path / "bad.py"
    good.write_text("def f() -> int:\n    return 1\n")
    bad.write_text("def f(:\n    return 1\n")

    assert compile_code(os.fspath(good) if as_str else good) is True
    assert compile_code(os.fspath(bad) if as_str else bad) is False
    assert any(f"Syntax error in {os.fspath(bad)!r}, line 1" in e for e in _errors(caplog)), _errors(caplog)


def test_existing_file_without_py_or_separator_is_still_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare name that is an existing file is read, not compiled as the identifier it spells."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myscript").write_text("def f(:\n")

    assert compile_code("myscript") is False


def test_empty_file_compiles_without_an_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """An empty module is valid Python, so it is True and logs nothing at ERROR."""
    path = tmp_path / "empty.py"
    path.touch()

    assert compile_code(path) is True
    assert _errors(caplog) == []


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read any file")
def test_unreadable_file_is_false_with_an_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A file that can't be opened is False with an error naming it, not an empty module that compiles."""
    path = tmp_path / "locked.py"
    path.write_text("x = 1\n")
    path.chmod(0)
    try:
        assert compile_code(path) is False
    finally:
        path.chmod(0o600)
    assert any(os.fspath(path) in e for e in _errors(caplog)), _errors(caplog)


def test_file_python_cannot_decode_is_false_unless_it_declares_its_encoding(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """CP1252 bytes are not UTF-8, so Python can't read the file as source, unless a coding line says cp1252."""
    plain, declared = tmp_path / "plain.py", tmp_path / "declared.py"
    body = 's = "“quoted”"\n'.encode("cp1252")
    plain.write_bytes(body)
    declared.write_bytes(b"# -*- coding: cp1252 -*-\n" + body)

    assert compile_code(plain) is False
    assert any(os.fspath(plain) in e for e in _errors(caplog)), _errors(caplog)
    assert compile_code(declared) is True


@pytest.mark.parametrize("as_str", [True, False], ids=["str", "pathlike"])
def test_directory_raises_is_a_directory(tmp_path: Path, as_str: bool) -> None:
    """A path to a folder is an argument error, like a missing file."""
    folder = tmp_path / "pkg"
    folder.mkdir()

    with pytest.raises(IsADirectoryError):
        compile_code(os.fspath(folder) if as_str else folder)


def test_pathlike_with_force_source_is_a_type_error(tmp_path: Path) -> None:
    """force_source=True with a Path is contradictory and refused."""
    with pytest.raises(TypeError, match="force_source"):
        compile_code(tmp_path / "x.py", force_source=True)
