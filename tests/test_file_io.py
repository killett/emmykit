"""`my_atomic_write`: contents, encoding, permissions, failure and locking."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

filelock = pytest.importorskip("filelock")

from emmykit.file_io import my_atomic_write  # noqa: E402


def _strays(directory: Path, target: Path) -> list[str]:
    """Return files left in `directory` besides `target` and its lock file."""
    keep = {target.name, target.name + ".lock"}
    return sorted(p.name for p in directory.iterdir() if p.name not in keep)


def test_write_mode_replaces_the_contents(tmp_path: Path) -> None:
    """"w" leaves exactly the new data, with no temp file behind."""
    path = tmp_path / "f.txt"
    path.write_text("old contents\n")

    my_atomic_write(path, "new\n", "w")

    assert path.read_text() == "new\n"
    assert _strays(tmp_path, path) == []


def test_append_mode_adds_after_the_existing_contents(tmp_path: Path) -> None:
    """"a" keeps what was there and adds the new data after it."""
    path = tmp_path / "f.txt"
    path.write_text("old\n")

    my_atomic_write(path, "new\n", "a")

    assert path.read_text() == "old\nnew\n"


def test_append_mode_creates_a_missing_file(tmp_path: Path) -> None:
    """"a" on a path that doesn't exist yet creates it, parent folder included."""
    path = tmp_path / "sub" / "f.txt"

    my_atomic_write(path, "first\n", "a")

    assert path.read_text() == "first\n"


def test_bytes_are_written_verbatim(tmp_path: Path) -> None:
    """Bytes skip encoding, so bytes that aren't valid text survive unchanged."""
    path = tmp_path / "f.bin"

    my_atomic_write(path, b"\xff\x00\xfe", "w")
    my_atomic_write(path, bytearray(b"\x01"), "a")

    assert path.read_bytes() == b"\xff\x00\xfe\x01"


def test_text_is_encoded_with_the_given_encoding(tmp_path: Path) -> None:
    """"é" is one byte, 0xE9, in CP1252, against two bytes in UTF-8."""
    path = tmp_path / "f.txt"

    my_atomic_write(path, "café", "w", encoding="cp1252")

    assert path.read_bytes() == b"caf\xe9"


def test_existing_file_keeps_its_permissions(tmp_path: Path) -> None:
    """Replacing the file keeps its mode, instead of the temp file's 0o600."""
    path = tmp_path / "f.txt"
    path.write_text("old\n")
    path.chmod(0o640)

    my_atomic_write(path, "new\n", "w")

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_new_file_gets_the_usual_permissions(tmp_path: Path) -> None:
    """A new file gets 0o666 minus the umask, like any other newly created file."""
    path = tmp_path / "f.txt"
    umask = os.umask(0o022)
    os.umask(umask)

    my_atomic_write(path, "new\n", "w")

    assert stat.S_IMODE(path.stat().st_mode) == 0o666 & ~umask


def test_failed_write_leaves_the_original_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that fails part-way changes nothing; the error still reaches the caller."""
    path = tmp_path / "f.txt"
    path.write_text("original\n")

    def disk_full(fd: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", disk_full)
    with pytest.raises(OSError, match="No space left"):
        my_atomic_write(path, "new\n", "w")

    assert path.read_text() == "original\n"
    assert _strays(tmp_path, path) == []


def test_lock_held_elsewhere_times_out_with_runtime_error(tmp_path: Path) -> None:
    """With the lock taken, a timeout ends in the documented RuntimeError and no write."""
    path = tmp_path / "f.txt"
    path.write_text("original\n")

    with filelock.FileLock(os.fspath(path) + ".lock"):
        with pytest.raises(RuntimeError, match="Could not acquire lock"):
            my_atomic_write(path, "new\n", "w", lock_timeout=0.05)

    assert path.read_text() == "original\n"
