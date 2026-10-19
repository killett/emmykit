"""`check_python_formatting`: the custom rules it reports through logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from emmykit.lint import check_python_formatting


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
