"""_version — extracted from univ_defs.py."""

from __future__ import annotations

from typing import Final

__all__ = ["__version__", "PY_VERSION"]

# Annotation deliberately omitted so hatchling's default version-extraction
# regex (`__version__\s*=\s*['"]([^'"]+)['"]`) can read this line.
__version__ = "0.3.4"

PY_VERSION: Final[float] = 3.12
