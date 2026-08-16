"""python_env — extracted from univ_defs.py."""

from __future__ import annotations

import os

from emmykit._version import PY_VERSION

def check_python_version(command: str) -> bool:
    """Check if the given Python command is available and has a version of PY_VERSION or higher."""
    import subprocess
    preferred_major = int(PY_VERSION)
    preferred_minor = int((PY_VERSION - preferred_major) * 100)
    result = subprocess.run([command, "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stdout.strip().split()[1]
        major, minor = map(int, version.split(".")[:2])
        if major == preferred_major and minor >= preferred_minor:
            return True
    return False

def find_preferred_python_version() -> str | None:
    """Find the command for the preferred version of python (stored here as PY_VERSION)."""
    # Check if the preferred python command (only specifying integer part of the preferred version) exists and returns a valid path
    import subprocess
    preferred_major       = int(PY_VERSION)
    preferred_python_path = subprocess.run(["which", f"python{preferred_major}"],
                                           capture_output=True, text=True).stdout.strip()
    if preferred_python_path and check_python_version(f"python{preferred_major}"):
        return os.path.basename(preferred_python_path)
    # Check if the preferred python command (with complete version specified) exists and returns a valid path
    preferred_python_path = subprocess.run(["which", f"python{PY_VERSION}"],
                                           capture_output=True, text=True).stdout.strip()
    if preferred_python_path and check_python_version(f"python{PY_VERSION}"):
        return os.path.basename(preferred_python_path)
    return None
