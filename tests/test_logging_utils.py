"""`return_method_name`: the caller's qualified name, as used in log messages."""

from __future__ import annotations

from emmykit.logging_utils import return_method_name


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
