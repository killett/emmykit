"""`my_diff`: which colour each kind of line is drawn in."""

from __future__ import annotations

import logging

import pytest

from emmykit.diff_view import my_diff

# A colour code no default uses, so its appearance proves the argument was honoured.
ADDED = "\x1b[95m"


@pytest.mark.parametrize("diff_choice", [0, 1])
def test_a_purely_added_line_uses_added_color(
    diff_choice: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A line present only in the new text is drawn in added_color.

    Fails if pure additions are hard-coded to red, the deleted-line default.
    """
    caplog.set_level(logging.INFO)

    my_diff("a\nb\n", "a\nb\nnew line\n", "f.txt", diff_choice=diff_choice, added_color=ADDED)

    added = [r.getMessage() for r in caplog.records if "new line" in r.getMessage()]
    assert len(added) == 1
    assert f"{ADDED}new line" in added[0]
