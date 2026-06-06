"""paths_ensure — extracted from univ_defs.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

def ensure_path(path: str | os.PathLike[str], absolute: bool = True) -> Path:
    """
    Ensure that the path is a Path. If not, make it a Path.

    Args:
        path:     The path to ensure is a Path object.
        absolute: If True (default), return an absolute path without resolving symlinks.

    Returns:
        A Path object (expanded for "~"). If absolute=True, it's absolute; otherwise it may be relative.
    """
    p = path if isinstance(path, Path) else Path(path)
    p = p.expanduser()  # always expand "~"
    return p.absolute() if absolute else p

_IS_PY_3_13: Final[bool] = sys.version_info >= (3, 13)
