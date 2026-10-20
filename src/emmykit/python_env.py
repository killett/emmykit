"""python_env — extracted from univ_defs.py."""

from __future__ import annotations

import os
import shutil
import subprocess

from emmykit._version import MIN_PYTHON_VERSION

# Asks the interpreter itself, rather than parsing `--version`, which is meant for people.
_VERSION_PROBE = "import sys; print(sys.version_info[0], sys.version_info[1])"
_PROBE_TIMEOUT_S = 10.0

def _python_version_of(command: str) -> tuple[int, int] | None:
    """
    Return the (major, minor) version of a Python command, or None if it can't be determined.

    Args:
        command: A command name looked up on PATH, or a path to an interpreter.

    Returns:
        The interpreter's (major, minor), or None if the command isn't found, fails,
        times out, or prints something other than two integers.
    """
    path = shutil.which(command)
    if path is None:
        return None
    try:
        # -I: isolated mode, so PYTHON* variables and user site-packages can't interfere.
        result = subprocess.run([path, "-I", "-c", _VERSION_PROBE], capture_output=True,
                                text=True, timeout=_PROBE_TIMEOUT_S, check=True)
        major, minor = (int(part) for part in result.stdout.split())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return major, minor

def check_python_version(command: str, minimum: tuple[int, int] = MIN_PYTHON_VERSION) -> bool:
    """
    Check whether a Python command exists and is at least a given (major, minor) version.

    Args:
        command: A command name looked up on PATH (e.g. "python3"), or a path to an interpreter.
        minimum: The lowest acceptable (major, minor) version (default MIN_PYTHON_VERSION).
                 There is no upper bound.

    Returns:
        True if the interpreter runs and its version is at or above 'minimum'; False if it is
        older, isn't found, or can't report its version within 10 seconds.
    """
    version = _python_version_of(command)
    return version is not None and version >= minimum

def find_python(minimum: tuple[int, int] = MIN_PYTHON_VERSION) -> str | None:
    """
    Find a Python interpreter on PATH that is at least a given (major, minor) version.

    Tries "python<major>" (e.g. "python3") first, then "python<major>.<minor>"
    (e.g. "python3.12"), and returns the first that passes check_python_version.

    Args:
        minimum: The lowest acceptable (major, minor) version (default MIN_PYTHON_VERSION).

    Returns:
        The interpreter's absolute path, or None if neither command qualifies.
    """
    major, minor = minimum
    for name in (f"python{major}", f"python{major}.{minor}"):
        path = shutil.which(name)
        if path is not None and check_python_version(path, minimum):
            return os.path.abspath(path)
    return None
