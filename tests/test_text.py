"""`emmykit.text`: `fix_mojibake` rewriting files on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ftfy")

from emmykit import text  # noqa: E402

# "café" encoded to UTF-8, misread as CP1252 and saved again as UTF-8.
MOJIBAKE = "cafÃ©\n".encode()


def _backups(path: Path) -> list[Path]:
    """Return the timestamped backups `fix_mojibake` left beside `path`."""
    return sorted(path.parent.glob(path.name + "_*.bak"))


def test_fixes_the_file_and_backs_up_the_original(tmp_path: Path) -> None:
    """The file ends up as clean UTF-8, and one backup holds the original bytes."""
    path = tmp_path / "note.txt"
    path.write_bytes(MOJIBAKE)

    text.fix_mojibake(path)

    assert path.read_bytes() == "café\n".encode()
    assert [b.read_bytes() for b in _backups(path)] == [MOJIBAKE]


def test_failed_write_leaves_the_original_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If writing the fixed text fails, the file is still there, unchanged.

    Fails if the backup is made by renaming the original away before the write.
    """
    path = tmp_path / "note.txt"
    path.write_bytes(MOJIBAKE)

    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(text, "my_atomic_write", disk_full)
    with pytest.raises(OSError, match="No space left"):
        text.fix_mojibake(path)

    assert path.read_bytes() == MOJIBAKE
