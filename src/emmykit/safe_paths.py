"""safe_paths — extracted from univ_defs.py."""

from __future__ import annotations

import errno
import logging
import os
from pathlib import Path

from emmykit.constants import IGNORE_THESE_ERRORS
from emmykit.logging_utils import return_method_name
from emmykit.paths_ensure import _IS_PY_3_13, ensure_path

def ensure_file(path: str | os.PathLike[str],
                raise_on_empty:  bool = False,
                allow_symlink:   bool = True,
                follow_symlinks: bool = True,
                verbose:         bool = True) -> Path:
    """
    Ensure that the given path is an existing file and return it as a Path object.

    Args:
        path:            The path to check.
        raise_on_empty:  If True,  raise an exception if the file is empty.
        allow_symlink:   If False, raise an exception if the path is a symlink.
        follow_symlinks: If False, do not follow symlinks when checking if it's a file.
                         If False, symlinks aren't considered files (even if allow_symlink=True).
                         With follow_symlinks=False, attribute reads (size/mtime/etc.) also don't
                         follow symlinks.
        verbose:         If True (default), log a warning if the file is empty or size is unknown.

    Returns:
        A Path object representing the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path exists but is a directory.
        ValueError:        If the path exists but is not a regular file, or if symlinks are not allowed.
        ValueError:        If raise_on_empty is True and the file is empty (or bad permissions, etc.)
    """
    p      = ensure_path(path)  # expanded + absolute, no symlink resolution
    exists = safe_exists(p, follow_symlinks=follow_symlinks)
    if not exists:
        raise FileNotFoundError(f"No such file: {os.fspath(p)}")
    if not allow_symlink and p.is_symlink():
        raise ValueError(f"Symlinks not allowed: {os.fspath(p)}")
    if not safe_is_file(p, follow_symlinks=follow_symlinks):
        if safe_is_dir( p, follow_symlinks=follow_symlinks):
            raise IsADirectoryError(f"Expected a file, got directory: {os.fspath(p)}")
        raise ValueError(f"Path exists but is not a regular file: {os.fspath(p)}")
    if (p_size := safe_size(p, follow_symlinks=follow_symlinks)) is not None:
        if raise_on_empty and p_size == 0:
            raise ValueError(f"BLAHFile is empty: {os.fspath(p)}")
        elif verbose and p_size == 0:
            logging.warning("BLAH2File is empty: %s", os.fspath(p))
    else:
        if raise_on_empty:
            raise ValueError(f"File size is unknown (permissions?): {os.fspath(p)}")
        elif verbose:
            logging.warning("File size is unknown (permissions?): %s", os.fspath(p))
    return p

def ensure_dir(path: str | os.PathLike[str],
               allow_symlink:   bool = True,
               follow_symlinks: bool = True) -> Path:
    """
    Ensure that the given path is an existing directory and return it as a Path object.

    Args:
        path:            The path to check.
        allow_symlink:   If False, raise an exception if the path is a symlink.
        follow_symlinks: If False, do not follow symlinks when checking if it's a directory.
                         If False, symlinks aren't considered directories (even if allow_symlink=True).
                         With follow_symlinks=False, attribute reads (size/mtime/etc.) also don't
                         follow symlinks.

    Returns:
        A Path object representing the directory.

    Raises:
        FileNotFoundError:  If the directory does not exist.
        NotADirectoryError: If the path exists but is not a directory.
    """
    p      = ensure_path(path)  # expanded + absolute, no symlink resolution
    exists = safe_exists(p, follow_symlinks=follow_symlinks)
    if not exists:
        raise FileNotFoundError(f"No such directory: {os.fspath(p)}")
    if not allow_symlink and p.is_symlink():
        raise ValueError(f"Symlinks not allowed: {os.fspath(p)}")
    if not safe_is_dir(p, follow_symlinks=follow_symlinks):
        raise NotADirectoryError(f"Expected a directory, got file: {os.fspath(p)}")
    return p

def _is_file(p: Path, follow_symlinks: bool) -> bool:
    """
    Version-proof 'is regular file?' that can avoid following symlinks.
    """
    if _IS_PY_3_13:  # 3.13+ supports follow_symlinks
        return p.is_file(follow_symlinks=follow_symlinks)
    if follow_symlinks:
        return p.is_file()
    try:
        import stat
        return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:
        return False

def _is_dir(p: Path, follow_symlinks: bool) -> bool:
    """
    Version-proof 'is directory?' that can avoid following symlinks.
    """
    if _IS_PY_3_13:  # 3.13+ supports follow_symlinks
        return p.is_dir(follow_symlinks=follow_symlinks)
    if follow_symlinks:
        return p.is_dir()
    try:
        import stat
        return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError:
        return False

def safe_exists(path: str | os.PathLike[str],
                follow_symlinks: bool = True) -> bool:
    """
    Like Path.exists()/os.path.lexists(), but doesn't raise on permission/loop errors.

    Args:
        path:            The path to check.
        follow_symlinks: If False, do not follow symlinks when checking if it exists.

    Returns:
        True if the path appears to exist (respecting follow_symlinks), False if it doesn't.
        For certain access/loop issues, returns True to avoid misclassifying as 'missing'.
    """
    p = path if isinstance(path, Path) else ensure_path(path)

    if not follow_symlinks:
        # lexists() doesn't raise for permission and treats a symlink itself as 'exists'
        return os.path.lexists(os.fspath(p))

    try:
        return p.exists()
    except PermissionError:
        # Treat as 'exists but inaccessible' to avoid raising FileNotFoundError upstream
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "%s: permission denied: %s", return_method_name(), os.fspath(p)
        )
        return True
    except OSError as e:
        # Fine-grained handling: missing vs. other transient/loop errors
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return False
        if e.errno in IGNORE_THESE_ERRORS:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "%s: suppressed errno=%s (%s): %s", return_method_name(),
                e.errno, getattr(errno, "errorcode", {}).get(e.errno, "?"), os.fspath(p)
            )
            # assume it exists but is problematic (loop, access, stale handle)
            return True
        raise

def safe_is_file(path: str | os.PathLike[str],
                 follow_symlinks: bool = True) -> bool:
    """
    Like Path.is_file(), but returns False on permission errors instead of raising.
    Uses _is_file() for pre-3.13 compatibility and no-follow mode.

    Args:
        path:            The file or directory path to check.
        follow_symlinks: Whether to follow symlinks (default: True).

    Returns:
        True if the path is a file, False otherwise.

    Raises:
        Intentionally designed to catch PermissionError, FileNotFoundError,
        some OSError variations. But not all.
    """
    p = path if isinstance(path, Path) else ensure_path(path)
    try:
        return _is_file(p, follow_symlinks=follow_symlinks)
    except PermissionError:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("safe_is_file: permission denied: %s", p)
        return False
    except OSError as e:
        if e.errno in IGNORE_THESE_ERRORS:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "%s: suppressed errno=%s (%s): %s", return_method_name(),
                e.errno, getattr(errno, "errorcode", {}).get(e.errno, "?"), p
            )
            return False
        raise

def safe_is_dir(path: str | os.PathLike[str],
                follow_symlinks: bool = True) -> bool:
    """
    Like Path.is_dir(), but returns False on permission errors instead of raising.
    Uses _is_dir() for pre-3.13 compatibility and no-follow mode.

    Args:
        path:            The file or directory path to check.
        follow_symlinks: Whether to follow symlinks (default: True).

    Returns:
        True if the path is a directory, False otherwise.

    Raises:
        Intentionally designed to catch PermissionError, FileNotFoundError,
        some OSError variations. But not all.
    """
    p = path if isinstance(path, Path) else ensure_path(path)
    try:
        return _is_dir(p, follow_symlinks=follow_symlinks)
    except PermissionError:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("safe_is_dir: permission denied: %s", p)
        return False
    except OSError as e:
        if e.errno in IGNORE_THESE_ERRORS:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "%s: suppressed errno=%s (%s): %s", return_method_name(),
                e.errno, getattr(errno, "errorcode", {}).get(e.errno, "?"), p
            )
            return False
        raise

def safe_stat(path: str | os.PathLike[str],
              follow_symlinks: bool = True) -> os.stat_result | None:
    """
    Like Path.stat()/lstat(), but returns None on permission/missing/loop errors.

    Args:
        path:            The file or directory path to stat.
        follow_symlinks: Whether to follow symlinks (default: True).
                         If true, uses Path.stat() else Path.lstat().

    Returns:
        An os.stat_result object or None if an error occurred.

    Raises:
        Intentionally designed to catch PermissionError, FileNotFoundError,
        some OSError variations. But not all.
    """
    p = path if isinstance(path, Path) else ensure_path(path)
    try:
        return p.stat() if follow_symlinks else p.lstat()
    except (PermissionError, FileNotFoundError):
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s: access/missing: %s",
                                                                          return_method_name(),
                                                                          os.fspath(p))
        return None
    except OSError as e:
        if e.errno in IGNORE_THESE_ERRORS:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "%s: suppressed errno=%s (%s): %s", return_method_name(),
                e.errno, getattr(errno, "errorcode", {}).get(e.errno, "?"), p
            )
            return None
        raise

def safe_size(path: str | os.PathLike[str],
              follow_symlinks: bool = True) -> int | None:
    """
    Like Path.stat().st_size, but returns None on permission/missing/loop errors.

    Args:
        path:            The file or directory path to stat().st_size
        follow_symlinks: Whether to follow symlinks (default: True).
                         If true, uses Path.stat() else Path.lstat().

    Returns:
        The size of the file in bytes or None if an error occurred.
    """
    st = safe_stat(path, follow_symlinks=follow_symlinks)
    return None if st is None else st.st_size

def safe_mtime(path: str | os.PathLike[str],
               follow_symlinks: bool = True,
               ns: bool = False) -> int | float | None:
    """
    Return mtime (seconds float or ns int) or None on errors.

    Args:
        path:            The file or directory path to stat().st_mtime
        follow_symlinks: Whether to follow symlinks (default: True).
                         If true, uses Path.stat() else Path.lstat().
        ns:              Whether to return the result in nanoseconds (default: False).

    Returns:
        The mtime of the file in seconds or nanoseconds, or None if an error occurred.
    """
    st = safe_stat(path, follow_symlinks=follow_symlinks)
    if st is None:
        return None
    return st.st_mtime_ns if ns else st.st_mtime

def safe_ctime(path: str | os.PathLike[str],
               follow_symlinks: bool = True,
               ns: bool = False) -> int | float | None:
    """
    Return ctime (seconds float or ns int) or None on errors.
    Note: On POSIX, ctime == inode *change* time, not creation time.
          On Windows, ctime is the file *creation* time.

    Args:
        path:            The file or directory path to stat().st_ctime
        follow_symlinks: Whether to follow symlinks (default: True).
                         If true, uses Path.stat() else Path.lstat().
        ns:              Whether to return the result in nanoseconds (default: False).

    Returns:
        The ctime of the file in seconds or nanoseconds, or None if an error occurred.
    """
    st = safe_stat(path, follow_symlinks=follow_symlinks)
    if st is None:
        return None
    return st.st_ctime_ns if ns else st.st_ctime
