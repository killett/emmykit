"""Helpers shared by more than one test module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import emmykit

SRC_DIR = Path(emmykit.__file__).resolve().parents[1]


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run `code` in a fresh interpreter that imports this checkout of emmykit.

    Args:
        code: Python source passed to `python -c`.

    Returns:
        The completed process, with text stdout and stderr captured.
    """
    path = [str(SRC_DIR), *filter(None, [os.environ.get("PYTHONPATH")])]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(path)}
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=120,
    )
