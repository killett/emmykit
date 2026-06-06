"""Extract one module's worth of symbols from univ_defs.py, verbatim.

Usage:
    python tools/extract_symbols.py <module_name>

Reads tools/_layout.json (written next to this file) which maps module
name -> list of top-level symbol names. Emits the source text of each
named symbol, in original file order, separated by a single blank line.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIV_DEFS = ROOT / "univ_defs.py"
LAYOUT = ROOT / "tools" / "_layout.json"

# Names imported from `typing` at the top of univ_defs.py.
_TYPING_NAMES: frozenset[str] = frozenset({
    "Any", "Final", "Literal", "Protocol", "TextIO", "Type",
    "TypeAlias", "Union", "overload",
})
# Names imported from `collections.abc` at the top of univ_defs.py.
_COLLECTIONS_ABC_NAMES: frozenset[str] = frozenset({
    "Callable", "Iterable", "Sequence",
})
# Combined regex alternation, used to scan the extracted body for any
# bare-word references to these names so the extractor can prepend the
# corresponding import lines.
_TYPING_REFERENCE_RE: re.Pattern[str] = re.compile(
    r"\b(" + "|".join(sorted(_TYPING_NAMES | _COLLECTIONS_ABC_NAMES)) + r")\b"
)


def _detect_typing_header(body: str) -> str:
    """Return import lines for any typing / collections.abc names used in body.

    Scans body for bare references to the names imported from `typing` or
    `collections.abc` at the top of univ_defs.py and emits the matching
    `from typing import ...` and/or `from collections.abc import ...`
    lines. Returns the empty string when no such names appear.

    Args:
        body: Joined source text of the symbols being extracted.

    Returns:
        Zero, one, or two import lines separated by newlines. When
        non-empty, the result is terminated with a newline so the caller
        can concatenate it directly in front of the body.
    """
    referenced = set(_TYPING_REFERENCE_RE.findall(body))
    if not referenced:
        return ""
    lines: list[str] = []
    abc_names = sorted(referenced & _COLLECTIONS_ABC_NAMES)
    typing_names = sorted(referenced & _TYPING_NAMES)
    if abc_names:
        lines.append(f"from collections.abc import {', '.join(abc_names)}")
    if typing_names:
        lines.append(f"from typing import {', '.join(typing_names)}")
    return "\n".join(lines) + "\n"


def main(module_name: str) -> None:
    layout = json.loads(LAYOUT.read_text())
    wanted = layout[module_name]  # list of top-level symbol names

    src = UNIV_DEFS.read_text()
    tree = ast.parse(src)

    # Map symbol name -> (lineno, end_lineno) for top-level defs/assigns.
    spans: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            spans[node.name] = (node.lineno, node.end_lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            spans[node.target.id] = (node.lineno, node.end_lineno)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    spans[t.id] = (node.lineno, node.end_lineno)
                elif isinstance(t, ast.Tuple):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            spans[e.id] = (node.lineno, node.end_lineno)

    lines = src.splitlines()
    chunks = []
    for sym in sorted(wanted, key=lambda s: spans[s][0]):
        a, b = spans[sym]
        chunks.append("\n".join(lines[a - 1 : b]))

    body = "\n\n".join(chunks) + "\n"
    header = _detect_typing_header(body)
    if header:
        sys.stdout.write(header + "\n" + body)
    else:
        sys.stdout.write(body)


if __name__ == "__main__":
    main(sys.argv[1])
