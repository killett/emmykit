"""`emmykit.html_files`: renaming by prefix, retitling and combining HTML files."""

from __future__ import annotations

from pathlib import Path

import pytest

from emmykit.html_files import remove_prefix_from_filename


def test_prefix_and_separators_are_removed_from_the_name(tmp_path: Path) -> None:
    """ "PFX_ - chapter.html" becomes "chapter.html"."""
    path = tmp_path / "PFX_ - chapter.html"
    path.write_text("x")

    assert remove_prefix_from_filename(path, "PFX") is True
    assert sorted(p.name for p in tmp_path.iterdir()) == ["chapter.html"]


@pytest.mark.parametrize("name", ["PFX", "PFX__", "PFX - "])
def test_a_name_that_is_only_the_prefix_is_left_alone(tmp_path: Path, name: str) -> None:
    """Removing the prefix would leave no name, so nothing is renamed.

    Fails with IndexError if the separator-stripping loop runs off the end.
    """
    path = tmp_path / name
    path.write_text("x")

    assert remove_prefix_from_filename(path, "PFX") is False
    assert path.exists()
