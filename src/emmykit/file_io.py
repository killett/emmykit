"""file_io — extracted from univ_defs.py."""

from __future__ import annotations

import os
from pathlib import Path

from typing import Literal

from emmykit.constants import DEFAULT_ENCODING
from emmykit.paths_ensure import ensure_path

def my_atomic_write(filepath: str | Path | os.PathLike[str], data: str | bytes | bytearray,
                    write_mode: Literal["w", "a"], encoding: str = DEFAULT_ENCODING,
                    lock_timeout: float | None = None,  # seconds to wait for lock (None = forever)
                    ) -> None:
    """
    Atomically write 'data' to 'filepath' with an advisory lock.

    - If write_mode="a" and file exists, data is appended.
    - If write_mode="a" and file does *not* exist, file is created.
    - A '.lock' file beside 'filepath' prevents concurrent writers.

    Args:
        filepath:     Path to the file to write.
        data:         Data to write (str or bytes).
        write_mode:   "w" for overwrite, "a" for append.
        encoding:     Encoding to use for text data (default: DEFAULT_ENCODING).
        lock_timeout: Maximum time to wait for the lock (default: None, meaning wait indefinitely).

    Returns:
        None: The file is written atomically.

    Raises:
        RuntimeError: If the lock cannot be acquired within the specified timeout.
    """
    from atomicwrites import atomic_write
    from filelock import FileLock, Timeout
    path = ensure_path(filepath)
    # ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    # choose text or binary mode
    is_bytes      = isinstance(data, (bytes, bytearray))
    mode          = write_mode + ("b" if is_bytes else "")
    text_enc      = None if is_bytes else encoding
    lock_path_str = os.fspath(path) + ".lock"
    lock          = FileLock(lock_path_str, timeout=lock_timeout)
    try:
        with lock:
            # atomicwrites will write to a temp file in the same dir then os.replace()
            # overwrite=(write_mode=="w") means "w" replaces, "a" appends
            with atomic_write(path, mode=mode, overwrite=(write_mode == "w"),
                              encoding=text_enc, preserve_mode=True) as f:
                f.write(data)
    except Timeout as e:
        raise RuntimeError(f"Could not acquire lock on {lock_path_str!r} within {lock_timeout} seconds") from e
