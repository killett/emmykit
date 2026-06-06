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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIV_DEFS = ROOT / "univ_defs.py"
LAYOUT = ROOT / "tools" / "_layout.json"


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

    sys.stdout.write("\n\n".join(chunks) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
