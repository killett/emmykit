"""Sanity tests for tools/generate_readme.py."""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

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


import tools.generate_readme as generate_readme  # noqa: E402
from tools.generate_readme import (  # noqa: E402
    GITHUB_BASE,
    SECTION_DROP_NOTES,
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


# ---- table-of-contents link tests ---- #


# How each place that shows the README turns a ``](#x)`` link and a raw
# ``<a id="x">`` into the page's href and id; a browser jumps to the first
# element whose id matches. Each entry is (link target, page id).
#   Local previews (VS Code and the like) use both as written.
#   GitHub prefixes ids with ``user-content-`` unless they already carry it,
#     keeps links as written, and its page script maps ``#x`` to
#     ``#user-content-x``.
#   PyPI's readme_renderer prefixes links, except footnote links (``fn-``,
#     ``fnref-``), and keeps raw ids as written.
_PREFIX = "user-content-"


def _github_id(anchor_id: str) -> str:
    """Return the id GitHub gives a raw ``<a id>``."""
    return anchor_id if anchor_id.startswith(_PREFIX) else _PREFIX + anchor_id


def _pypi_link(target: str) -> str:
    """Return the fragment PyPI links ``#target`` to."""
    return target if target.startswith(("fn-", "fnref-")) else _PREFIX + target


RENDERERS: dict[str, tuple[Callable[[str], str], Callable[[str], str]]] = {
    "local-preview": (lambda target: target, lambda anchor_id: anchor_id),
    "github": (lambda target: _PREFIX + target, _github_id),
    "pypi": (_pypi_link, lambda anchor_id: anchor_id),
}

_ANCHOR = re.compile(r'<a id="([^"]+)"></a>')
# What an anchor sits on: any further anchors, then a symbol's <details>
# block or a module heading.
_ENTRY = re.compile(
    r'(?:<a id="[^"]+"></a>)*\n'
    r"(?:<details>\n<summary><code>([^<]+)</code>|### `([^`]+)`)"
)


def _toc_links(text: str) -> list[tuple[str, str]]:
    """Return (name shown, link target) for each table-of-contents link."""
    toc = text.split("## Table of contents", 1)[1].split("## API reference", 1)[0]
    return re.findall(r"^ *- \[`([^`]+)`[^\]]*\]\(#([^)]+)\)", toc, re.M)


def _entry_names_by_id(text: str, page_id: Callable[[str], str]) -> dict[str, str | None]:
    """Map each page id to the name of the entry under its first anchor."""
    names: dict[str, str | None] = {}
    for anchor in _ANCHOR.finditer(text):
        entry = _ENTRY.match(text, anchor.end())
        name = (entry.group(1) or entry.group(2)) if entry else None
        names.setdefault(page_id(anchor.group(1)), name)
    return names


@pytest.mark.parametrize("renderer", RENDERERS)
def test_every_toc_link_lands_on_the_entry_it_names(renderer: str) -> None:
    """Each contents link jumps to the entry whose name it shows, wherever the README is read."""
    link_target, page_id = RENDERERS[renderer]
    text = build_readme()
    links = _toc_links(text)
    names = _entry_names_by_id(text, page_id)
    misses = [
        (name, target, names.get(link_target(target), "<no such id>"))
        for name, target in links
        if names.get(link_target(target)) != name
    ]
    assert ("constants", "m-constants") in links  # the parse found the contents
    assert misses == []


def test_intro_counts_the_public_surface() -> None:
    """The intro's name count matches the curated public surface instead of drifting."""
    baseline = Path(__file__).parent / "_baseline_signatures.json"
    count = len(json.loads(baseline.read_text()))
    assert f"Personal Python utility kit: {count} importable" in build_readme()


def _patch_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, edit: Callable[[dict[str, list[str]]], None]
) -> None:
    """Point the generator at a copy of ``_layout.json`` changed by ``edit``."""
    layout = json.loads(generate_readme.LAYOUT_PATH.read_text())
    edit(layout)
    path = tmp_path / "_layout.json"
    path.write_text(json.dumps(layout))
    monkeypatch.setattr(generate_readme, "LAYOUT_PATH", path)


def test_public_name_missing_from_layout_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A public name with no module in ``_layout.json`` stops the build instead of vanishing."""
    _patch_layout(monkeypatch, tmp_path, lambda layout: layout["inflect_utils"].remove("my_plural"))
    with pytest.raises(ValueError, match="my_plural"):
        build_readme()


def test_public_name_mapped_to_the_wrong_module_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A name filed under a module that doesn't define it stops the build instead of vanishing."""
    def move(layout: dict[str, list[str]]) -> None:
        layout["inflect_utils"].remove("my_plural")
        layout["text"].append("my_plural")

    _patch_layout(monkeypatch, tmp_path, move)
    with pytest.raises(ValueError, match="my_plural"):
        build_readme()


def test_module_missing_from_layer_order_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A module left out of LAYER_ORDER stops the build instead of losing all its names."""
    kept = [(layer, m) for layer, m in generate_readme.LAYER_ORDER if m != "inflect_utils"]
    monkeypatch.setattr(generate_readme, "LAYER_ORDER", kept)
    with pytest.raises(ValueError, match="inflect_utils"):
        build_readme()


# Constants whose rendered value depends on the machine that generates the README.
_HOST_DEPENDENT = ("COMPUTER_NAME", "IS_NASA_COMPUTER")


def _mask_host_values(text: str) -> str:
    """Replace the rendered values of the host-dependent constants with ``<host>``."""
    for name in _HOST_DEPENDENT:
        text = re.sub(rf"(\b{name}(?:</code> —|:) \w+ = )[^<\n]+", r"\1<host>", text)
    return text


def test_readme_matches_generator() -> None:
    """README.md is what the generator produces now, apart from host-dependent values.

    Nothing runs ``generate_readme.py --check``, and it would fail on any other
    machine anyway, so without this a docstring or surface change could ship
    with a stale README.
    """
    readme = _mask_host_values((ROOT / "README.md").read_text()).splitlines()
    generated = _mask_host_values(build_readme()).splitlines()
    diff = list(difflib.unified_diff(readme, generated, "README.md", "generated", lineterm="", n=1))
    assert diff == [], "README.md is stale; run tools/generate_readme.py:\n" + "\n".join(diff[:40])
