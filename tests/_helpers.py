"""Helpers shared by more than one test module."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import emmykit
from emmykit.palette import Palette

SRC_DIR = Path(emmykit.__file__).resolve().parents[1]

# An uppercase #RRGGBB colour, the form every palette colour is stored in.
HEX_RE = re.compile(r"^#[0-9A-F]{6}$")


def all_palette_colors(pal: Palette) -> list[str]:
    """Return every colour a palette carries: series colours plus roles."""
    return [*pal.series, pal.background, pal.foreground, pal.grid]


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
