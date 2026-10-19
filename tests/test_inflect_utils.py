"""`my_plural`'s fallback rules, used when the `inflect` package isn't installed."""

from __future__ import annotations

import pytest

from emmykit import inflect_utils


@pytest.fixture(autouse=True)
def without_inflect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the inflect engine unavailable, as in an install without the extra."""
    def missing() -> object:
        raise ImportError("No module named 'inflect'")

    monkeypatch.setattr(inflect_utils, "_get_inflect_engine", missing)


@pytest.mark.parametrize(
    ("word", "plural"),
    [("chief", "chiefs"), ("roof", "roofs"), ("belief", "beliefs"), ("chef", "chefs"),
     ("cliff", "cliffs"), ("proof", "proofs"), ("brief", "briefs")],
)
def test_f_words_listed_as_exceptions_just_add_s(word: str, plural: str) -> None:
    """The listed exceptions keep their f. Fails if the list is checked against the stem."""
    assert inflect_utils.my_plural(2, word) == f"2 {plural}"


@pytest.mark.parametrize(
    ("word", "plural"),
    [("knife", "knives"), ("life", "lives"), ("leaf", "leaves"), ("wolf", "wolves")],
)
def test_other_f_and_fe_words_take_ves(word: str, plural: str) -> None:
    """Words not on the exception list still follow the f/fe -> ves rule."""
    assert inflect_utils.my_plural(3, word) == f"3 {plural}"
