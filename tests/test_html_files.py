"""`emmykit.html_files`: renaming by prefix, retitling and combining HTML files."""

from __future__ import annotations

from pathlib import Path

import pytest

from emmykit.html_files import remove_prefix_from_filename, remove_prefix_from_html_title


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


def test_title_with_attributes_loses_its_prefix(tmp_path: Path) -> None:
    """A <title> tag with attributes is found too."""
    path = tmp_path / "ch1.html"
    path.write_text('<html><head><title lang="en">Ch 1: Intro</title></head></html>')

    assert remove_prefix_from_html_title(path, "Ch 1: ") is True
    assert path.read_text() == '<html><head><title lang="en">Intro</title></head></html>'


def test_page_without_a_title_is_reported_and_left_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No <title> means False and a warning, not a slice of whatever follows."""
    path = tmp_path / "ch1.html"
    path.write_text("<html><body>Ch 1: no title here</body></html>")

    assert remove_prefix_from_html_title(path, "Ch 1: ") is False
    assert "Could not find the title" in caplog.text


def test_cp1252_page_is_written_back_in_cp1252(tmp_path: Path) -> None:
    """The page keeps the encoding it declares; only the prefix bytes go.

    Fails if it is rewritten as UTF-8 ("é" as C3 A9) under its windows-1252 meta tag.
    """
    path = tmp_path / "ch1.html"
    path.write_bytes(b'<meta charset="windows-1252"><title>Ch 1: Caf\xe9</title>')

    assert remove_prefix_from_html_title(path, "Ch 1: ") is True
    assert path.read_bytes() == b'<meta charset="windows-1252"><title>Caf\xe9</title>'
