"""file_io — extracted from univ_defs.py."""

from __future__ import annotations

import os
import secrets
import stat
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

    The new contents go to a temp file in the same folder, which is flushed to
    disk and then renamed over 'filepath', so readers see the old file or the
    new one, never a partial write. An existing file keeps its permissions.

    - If write_mode="a" and file exists, data is appended (the old contents
      and the new data are written out together).
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
        OSError:      If writing fails; 'filepath' is then left as it was.
    """
    from filelock import FileLock, Timeout
    path = ensure_path(filepath)
    # ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    payload       = bytes(data) if isinstance(data, (bytes, bytearray)) else data.encode(encoding)
    lock_path_str = os.fspath(path) + ".lock"
    # filelock waits indefinitely for a negative timeout and rejects None.
    lock          = FileLock(lock_path_str, timeout=-1 if lock_timeout is None else lock_timeout)
    try:
        with lock:
            _replace_atomically(path, payload, append=(write_mode == "a"))
    except Timeout as e:
        raise RuntimeError(f"Could not acquire lock on {lock_path_str!r} within {lock_timeout} seconds") from e

def _replace_atomically(path: Path, payload: bytes, append: bool) -> None:
    """
    Replace 'path' with 'payload', or with its current contents plus 'payload' if 'append'.

    Args:
        path:    The file to replace; it need not exist yet.
        payload: The bytes to write.
        append:  Keep the current contents in front of 'payload'.

    Raises:
        OSError: If any step fails; the temp file is removed and 'path' is untouched.
    """
    try:
        old_mode: int | None = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        old_mode = None
    contents = (path.read_bytes() if append and old_mode is not None else b"") + payload
    # Same folder, so os.replace is a rename within one filesystem. Mode 0o666
    # lets the umask decide, as for any new file; tempfile would force 0o600.
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd  = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        if old_mode is not None:
            os.chmod(tmp, old_mode)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    # Make the rename itself durable.
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
