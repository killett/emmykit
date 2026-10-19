"""`logging_utils`: caller names for log messages, `configure_logging` and `MaxLevelFilter`."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from emmykit.logging_utils import MaxLevelFilter, configure_logging, return_method_name


def plain_function() -> str:
    """Return this function's name as `return_method_name` sees it."""
    return return_method_name()


def outer_function() -> str:
    """Return the name of a function defined inside this one."""
    def inner() -> str:
        """Report its own name."""
        return return_method_name()

    return inner()


def caller_of_helper() -> str:
    """Ask a helper for *this* function's name, one frame up."""
    return _helper_one_level_down()


def _helper_one_level_down() -> str:
    """Return the name of whoever called this helper."""
    return return_method_name(levels_up=2)


class Widget:
    """A class with one of each kind of method."""

    def method(self) -> str:
        """Report an instance method's name."""
        return return_method_name()

    @classmethod
    def class_method(cls) -> str:
        """Report a classmethod's name."""
        return return_method_name()

    @staticmethod
    def static_method() -> str:
        """Report a staticmethod's name."""
        return return_method_name()


def test_names_each_kind_of_caller() -> None:
    """Functions by name; methods of every kind as Class.method; nested without <locals>."""
    assert plain_function() == "plain_function"
    assert outer_function() == "outer_function.inner"
    assert Widget().method() == "Widget.method"
    assert Widget.class_method() == "Widget.class_method"
    assert Widget.static_method() == "Widget.static_method"


def test_levels_up_names_a_caller_further_up() -> None:
    """levels_up=2 skips the helper and names the function that called it."""
    assert caller_of_helper() == "caller_of_helper"


# --- configure_logging and MaxLevelFilter -------------------------------------

@pytest.fixture
def root_with_sentinel() -> Iterator[tuple[logging.Logger, logging.Handler]]:
    """Give the root logger one known handler for the test, restoring it afterwards."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    sentinel = logging.NullHandler()
    root.handlers = [sentinel]
    yield root, sentinel
    for handler in root.handlers:
        if handler not in saved_handlers:
            handler.close()
    root.handlers, root.level = saved_handlers, saved_level


def test_configure_logging_keeps_existing_handlers_when_log_files_fail(
    tmp_path: Path, root_with_sentinel: tuple[logging.Logger, logging.Handler],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the second log file can't be opened, nothing changes and the first is closed.

    Fails if the root handlers are cleared before the files are opened, which
    leaves the program with no logging at all, or if the first file is leaked.
    """
    root, sentinel = root_with_sentinel
    opened: list[logging.FileHandler] = []

    class SecondFails(logging.FileHandler):
        """A FileHandler whose second construction fails, like a full disk."""

        def __init__(self, filename: str, *args: object, **kwargs: object) -> None:
            if opened:
                raise OSError(28, "No space left on device")
            super().__init__(filename, *args, **kwargs)  # type: ignore[arg-type]
            opened.append(self)

    monkeypatch.setattr(logging, "FileHandler", SecondFails)
    before = root.handlers[:]  # the sentinel, plus pytest's own capture handlers
    assert sentinel in before

    assert configure_logging("demo", logdir=tmp_path) is None
    assert root.handlers == before
    assert opened[0].stream is None  # closed


def test_max_level_filter_is_a_complete_logging_filter() -> None:
    """It initializes logging.Filter, so it has a name, and it passes records up to its level."""
    flt = MaxLevelFilter(logging.WARNING)
    warning = logging.LogRecord("x", logging.WARNING, __file__, 1, "w", None, None)
    error = logging.LogRecord("x", logging.ERROR, __file__, 1, "e", None, None)

    assert flt.name == ""
    assert flt.filter(warning) and not flt.filter(error)
