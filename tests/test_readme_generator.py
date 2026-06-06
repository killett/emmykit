"""Sanity tests for tools/generate_readme.py."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.generate_readme import SymbolInfo, _render_symbol  # noqa: E402


def _sym(docstring: str | None) -> SymbolInfo:
    return SymbolInfo(
        name="parse_datetime",
        module="datetime_utils",
        kind="function",
        summary="Parse a date.",
        signature="parse_datetime(s: str) -> datetime",
        docstring=docstring,
        value_preview=None,
        annotation=None,
        method_names=None,
        dataclass_field_names=None,
        source_line=10,
    )


def test_docstring_wrapped_in_text_fence() -> None:
    """Non-empty docstring is emitted as a fenced ```text block."""
    doc = "Summary line.\n\nArgs:\n    x:  the input\n    y:  the other\n"
    out = _render_symbol(_sym(doc))
    assert "```text\n" in out, "missing opening text fence"
    assert "    y:  the other\n```" in out, "closing fence not flush against content"


def test_empty_docstring_emits_no_fence() -> None:
    """Symbols without a docstring must not produce a fence."""
    out = _render_symbol(_sym(None))
    assert "```text" not in out
