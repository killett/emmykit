"""`treeview_new_files`: which files count as new."""

from __future__ import annotations

import os
from pathlib import Path

from emmykit.treeview import treeview_new_files


def _age(path: Path, mtime: float) -> None:
    """Set both access and modification times of `path`."""
    os.utime(path, (mtime, mtime))


def test_last_mtime_alone_sets_the_cutoff(tmp_path: Path) -> None:
    """With no last_file_path, last_mtime decides what is new.

    Fails if last_mtime is overwritten with 0, which makes every file new.
    """
    old = tmp_path / "old.txt"
    old.write_text("old\n")
    _age(old, 1_000)
    _age(tmp_path, 1_000)

    assert treeview_new_files(tmp_path, last_mtime=2_000, print_root=False) is False
    assert treeview_new_files(tmp_path, last_mtime=500, print_root=False) is True


def test_no_cutoff_means_everything_is_new(tmp_path: Path) -> None:
    """Without last_file_path or last_mtime, any file is relevant."""
    old = tmp_path / "old.txt"
    old.write_text("old\n")
    _age(old, 1_000)
    _age(tmp_path, 1_000)

    assert treeview_new_files(tmp_path, print_root=False) is True
