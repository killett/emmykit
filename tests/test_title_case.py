"""`my_title_case`: capitalizing the first letter of each word."""

from __future__ import annotations

import pytest

from emmykit.text import my_title_case


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("don't stop me now", "Don't Stop Me Now"),
        ("the 2nd act", "The 2nd Act"),
        ("well-known facts", "Well-Known Facts"),
        ("(hello) world", "(Hello) World"),
        ("WW2 and iZombie", "WW2 And iZombie"),
        ("the lord of the rings", "The Lord Of The Rings"),
    ],
)
def test_my_title_case_capitalizes_the_first_letter_of_each_word(title: str, expected: str) -> None:
    """Only a word's first letter (and each hyphenated part's) changes.

    Fails if str.title() is used, which also capitalizes the letter after an
    apostrophe or a digit ("Don'T", "2Nd").
    """
    assert my_title_case(title) == expected
