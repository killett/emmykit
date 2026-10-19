"""`check_python_formatting`: the custom rules it reports through logging."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from emmykit.lint import ask_and_autopep8, check_python_formatting, interactive_flake8
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
