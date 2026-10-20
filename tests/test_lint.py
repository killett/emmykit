"""`lint`: `check_python_formatting`'s rules, the flake8/autopep8 helpers and `multireplace`."""

from __future__ import annotations

import argparse
import builtins
import logging
import os
import subprocess
from pathlib import Path

import pytest

from emmykit.lint import ask_and_autopep8, check_python_formatting, interactive_flake8, multireplace
from emmykit.options import Options


def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the messages logged at ERROR level."""
    return [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]


def test_function_without_hints_or_docstring_is_reported(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing type hints and a missing docstring each produce an error naming the function."""
    path = tmp_path / "bad.py"
    path.write_text("def add(a, b):\n    return a + b\n")
    caplog.set_level(logging.INFO)

    assert check_python_formatting(path) is True

    errors = _errors(caplog)
    assert any('"add": no docstring' in e for e in errors), errors
    assert any('add: missing type hints for param "a", param "b", return' in e for e in errors), errors


def test_conforming_function_is_not_reported(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A hinted, documented function produces no errors."""
    path = tmp_path / "good.py"
    path.write_text('def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n')
    caplog.set_level(logging.INFO)

    assert check_python_formatting(path) is True

    assert _errors(caplog) == []


CLEAN = '"""A module."""\n\n\ndef add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n'


def test_check_python_formatting_logs_no_note_to_self(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A clean file produces no leftover developer reminder at WARNING level."""
    path = tmp_path / "good.py"
    path.write_text(CLEAN)
    caplog.set_level(logging.INFO)

    check_python_formatting(path)

    assert not [r.getMessage() for r in caplog.records if "LOOK FOR" in r.getMessage()]


def test_interactive_flake8_stops_early_on_a_clean_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No violations means "nothing to do" and no further flake8 or autopep8 runs.

    Fails if flake8's Report, which is always truthy, is tested for truth
    instead of its error count.
    """
    pytest.importorskip("flake8")
    path = tmp_path / "clean.py"
    path.write_text(CLEAN)
    caplog.set_level(logging.INFO)

    assert interactive_flake8(Options(), path) is True
    assert "No flake8 errors—nothing to do." in caplog.text


def test_ask_and_autopep8_names_an_empty_file(tmp_path: Path) -> None:
    """The ValueError for an empty file reads "Empty file: <path>", not a tuple."""
    pytest.importorskip("autopep8")
    path = tmp_path / "empty.py"
    path.touch()

    with pytest.raises(ValueError) as excinfo:
        ask_and_autopep8(path, "E302")

    assert str(excinfo.value) == f"Empty file: {os.fspath(path)}"


def test_ask_and_autopep8_reports_a_bad_diff_choice(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-integer diff_choice is logged by value and refused.

    Fails if the message formats it with %d, which raises inside logging.
    """
    pytest.importorskip("autopep8")
    path = tmp_path / "e302.py"
    path.write_text("def a():\n    pass\ndef b():\n    pass\n")
    caplog.set_level(logging.INFO)

    assert ask_and_autopep8(path, "E302", diff_choice="unified") is False  # type: ignore[arg-type]
    assert "Invalid diff_choice='unified'" in caplog.text


def test_flake8_that_cannot_run_is_an_error_not_a_clean_bill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the flake8 command fails, interactive_flake8 raises instead of finding nothing."""
    pytest.importorskip("flake8")
    path = tmp_path / "e302.py"
    path.write_text("def a():\n    pass\ndef b():\n    pass\n")

    def no_flake8(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "/usr/bin/python3: No module named flake8\n")

    monkeypatch.setattr(subprocess, "run", no_flake8)
    with pytest.raises(RuntimeError, match="No module named flake8"):
        interactive_flake8(Options(), path)


# --- multireplace raises instead of exiting the process ----------------------

def _replace_options(glob_pattern: str, directory: Path) -> Options:
    """Options as multireplace's command line would set them: replace "old" with "new"."""
    options = Options()
    options.args = argparse.Namespace(old_str="old", new_str="new", glob_pattern=glob_pattern,
                                      dir=os.fspath(directory), recursive=False)
    return options


@pytest.mark.parametrize(
    ("glob_pattern", "where", "error", "message"),
    [
        ("  ", ".", ValueError, r"^glob_pattern must be a non-empty string\.$"),
        ("*.txt", "missing", FileNotFoundError, r"^Directory does not exist: .*missing$"),
        ("*.txt", "a.txt", NotADirectoryError, r"^Path is not a directory: .*a\.txt$"),
    ],
    ids=["blank-glob", "missing-dir", "file-as-dir"],
)
def test_multireplace_raises_the_documented_errors(
    tmp_path: Path, glob_pattern: str, where: str, error: type[Exception], message: str
) -> None:
    """Bad arguments raise the errors the docstring lists, instead of sys.exit(2)."""
    (tmp_path / "a.txt").write_text("old\n")

    with pytest.raises(error, match=message):
        multireplace(_replace_options(glob_pattern, tmp_path / where))


def test_multireplace_passes_ctrl_c_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ctrl-C at the confirmation prompt is re-raised as KeyboardInterrupt, not sys.exit(130)."""
    path = tmp_path / "a.txt"
    path.write_text("old\n")

    def interrupt(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupt)
    with pytest.raises(KeyboardInterrupt):
        multireplace(_replace_options("*.txt", tmp_path))

    assert "Interrupted by user." in [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert path.read_text() == "old\n"


def test_one_line_file_with_a_slash_is_compiled_as_code(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """check_python_formatting compiles the file, not its text taken as a path.

    `x = 1/2` with no newline looks like a path to compile_code, so passing
    the text instead of the file would raise FileNotFoundError.
    """
    path = tmp_path / "one.py"
    path.write_text("x = 1/2")
    caplog.set_level(logging.INFO)

    assert check_python_formatting(path) is True
    assert f"✅ {path} compiled successfully." in caplog.text
