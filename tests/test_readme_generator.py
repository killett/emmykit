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


# ---- render policy tests ---- #


from tools.generate_readme import (  # noqa: E402
    CondenseGroup,
    GITHUB_BASE,
    ModuleRenderRule,
    RENDER_RULES,
    SECTION_DROP_NOTES,
    _render_condense_group,
    build_readme,
)


def test_source_link_is_absolute() -> None:
    """_render_symbol emits a github.com/.../blob/main URL, not a relative path."""
    out = _render_symbol(_sym("Stub docstring."))
    assert f"[source ↗]({GITHUB_BASE}/src/emmykit/datetime_utils.py" in out
    assert "[source ↗](src/" not in out


def test_omit_drops_symbol_from_built_readme() -> None:
    """A symbol listed in RENDER_RULES[module].omit must not appear as an individual entry."""
    text = build_readme()
    # LDQUOTE is omitted; assert no per-symbol anchor for it.
    assert '<a id="ldquote"></a>' not in text
    # Sanity: DEFAULT_ENCODING (KEEP) still present.
    assert '<a id="default_encoding"></a>' in text


def test_condense_emits_single_block() -> None:
    """ANSI_* family collapses to exactly one condense block; no per-color anchors remain."""
    text = build_readme()
    assert text.count('<a id="c-constants-ansi-color-escapes"></a>') == 1
    assert '<a id="ansi_cyan"></a>' not in text
    assert '<a id="ansi_red"></a>' not in text
    # The condense block lists the absorbed names in its **Includes:** line.
    assert "**Includes:** `ANSI_CYAN`, `ANSI_GREEN`, `ANSI_RED`, `ANSI_RESET`, `ANSI_YELLOW`." in text


def test_drop_section_skipped_in_toc_and_body() -> None:
    """drop_section modules produce no module anchor or section heading."""
    text = build_readme()
    assert '<a id="m-net_targets"></a>' not in text
    assert '<a id="m-text_constants"></a>' not in text
    assert "### `net_targets`" not in text
    assert "### `text_constants`" not in text


def test_section_note_injected_into_downstream_section() -> None:
    """Notes from dropped sections appear in their downstream module's body."""
    text = build_readme()
    # net_targets -> network
    expected_net = SECTION_DROP_NOTES["net_targets"][1]
    expected_text = SECTION_DROP_NOTES["text_constants"][1]
    assert expected_net in text
    assert expected_text in text
