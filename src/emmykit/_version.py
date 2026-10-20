"""_version — extracted from univ_defs.py."""

from __future__ import annotations

from typing import Final

__all__ = ["__version__", "MIN_PYTHON_VERSION"]

# Annotation deliberately omitted so hatchling's default version-extraction
# regex (`__version__\s*=\s*['"]([^'"]+)['"]`) can read this line.
__version__ = "0.7.0"

# Compare with sys.version_info (`sys.version_info >= MIN_PYTHON_VERSION`).
# tests/test_python_env.py keeps it equal to requires-python in pyproject.toml.
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 12)  # oldest (major, minor) emmykit supports
