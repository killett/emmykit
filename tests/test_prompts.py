"""`prompt_then_choose`, with `input()` replaced by scripted answers."""

from __future__ import annotations

import builtins
from collections.abc import Iterator

import pytest

from emmykit.prompts import prompt_then_choose


def _answers(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    """Make input() return `answers` in turn; return the list of prompts it was shown."""
    queue: Iterator[str] = iter(answers)
    shown: list[str] = []

    def fake_input(prompt: str = "") -> str:
        shown.append(prompt)
        return next(queue)

    monkeypatch.setattr(builtins, "input", fake_input)
    return shown


def test_enter_picks_an_empty_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty-string default is offered, so pressing Enter returns it.

    Fails if the prompt shows the default (checked with `is not None`) but
    Enter is refused (checked by truthiness).
    """
    shown = _answers(monkeypatch, "")

    assert prompt_then_choose("Pick one", ["a", "b"], default="") == ""
    assert shown == ["Select [1-2] (default ): "]


def test_enter_without_a_default_asks_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no default, Enter is invalid and the question is repeated."""
    shown = _answers(monkeypatch, "", "2")

    assert prompt_then_choose("Pick one", ["a", "b"]) == "b"
    assert shown == ["Select [1-2]: ", "Select [1-2]: "]
