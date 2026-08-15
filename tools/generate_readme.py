"""Regenerate /workspace/emmykit/README.md from the live emmykit package.

Idempotent. Stdlib-only. Re-run after any public-surface change.

Usage:
    python tools/generate_readme.py             # writes ./README.md
    python tools/generate_readme.py --check     # exits non-zero if README is stale
    python tools/generate_readme.py --stdout    # prints generated README to stdout
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import io
import json
import pprint
import re
import sys
import textwrap
import tokenize
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src" / "emmykit"
LAYOUT_PATH = ROOT / "tools" / "_layout.json"
README_PATH = ROOT / "README.md"

# Inserted at import-time into __all__ in src/emmykit/__init__.py for byte-for-byte
# parity with the legacy `from univ_defs import *` surface. They are stdlib names,
# not emmykit's own code. Omit them from the README.
STDLIB_REEXPORTS: frozenset[str] = frozenset({
    "Any", "Callable", "Enum", "Final", "Iterable", "Literal", "Path", "Protocol",
    "Sequence", "TextIO", "ThreadPoolExecutor", "Type", "TypeAlias", "annotations",
    "chain", "dataclass", "errno", "field", "logging", "os", "overload", "re",
    "replace", "sys",
})

# Layer ordering (L0 -> L8) baked in so the README sections come out top-down.
LAYER_ORDER: list[tuple[int, str]] = [
    (0, "constants"),
    (0, "extensions"),
    (0, "net_targets"),
    (0, "embedded_scripts"),
    (1, "_version"),
    (1, "options"),
    (1, "text_constants"),
    (1, "inflect_utils"),
    (1, "logging_utils"),
    (1, "paths_ensure"),
    (2, "safe_paths"),
    (2, "file_io"),
    (3, "io_subprocess"),
    (4, "prompts"),
    (4, "introspection"),
    (4, "humanize"),
    (1, "numeric_helpers"),
    (4, "datetime_utils"),
    (4, "json_io"),
    (4, "diff_view"),
    (5, "text"),
    (5, "hosts"),
    (5, "network"),
    (5, "python_env"),
    (5, "files"),
    (6, "lint"),
    (7, "treeview"),
    (7, "docker_utils"),
    (7, "system"),
    (7, "media"),
    (7, "html_files"),
    (8, "llm"),
]

# `module: (descriptive subtitle, 1-2 sentence intro)`.
MODULE_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "constants":        ("ANSI colors, unicode punctuation, default encoding, ignore-lists",
                         "Terminal escape codes, curly quotes, the em-dash, the package's UTF-8 default, the set of "
                         "errno codes treated as benign by `safe_*`, and the flake8/autopep8 codes Emmy deliberately ignores."),
    "extensions":       ("File-extension lookup tables (audio / video / image / book / text / html / playlist / archive / subtitle)",
                         "Lists and frozensets of common file extensions per media kind, plus an `ALL_KNOWN_EXTENSIONS` umbrella and "
                         "the canonical `TEXT_ENCODINGS` ordering used by `my_fopen` when sniffing."),
    "net_targets":      ("Network-diagnostic probe targets",
                         "IPv4, IPv6, HTTP, and DNS endpoint lists used by `is_internet_available` to verify connectivity beyond DNS resolution."),
    "embedded_scripts": ("Pre-packaged helper-script source-strings",
                         "Python script literals shipped as importable strings — used by Emmy's external automation "
                         "to drop drop-in helpers into other projects."),
    "_version":         ("Package and Python version constants",
                         "Single source of truth for `emmykit.__version__` (read by hatchling at build-time) and the supported `PY_VERSION` floor."),
    "options":          ("Options dataclasses for configuration",
                         "Aggregated runtime/plot-time settings passed through downstream APIs as a single object."),
    "text_constants":   ("Translation tables for text normalization",
                         "Character maps used by `normalize_for_search` to fold quotes, ellipses, and other punctuation into ASCII equivalents."),
    "numeric_helpers":  ("Numeric parsing + unit-to-seconds conversion",
                         "Tiny helpers shared by `humanize` and `datetime_utils` so neither has to pull in the other."),
    "paths_ensure":     ("Path normalization",
                         "Leaf helper that coerces `os.PathLike` / `str` arguments into resolved `Path` objects."),
    "inflect_utils":    ("Grammar + pluralization helpers",
                         "Lazy wrapper over the `inflect` package with a stdlib-only fallback table for common nouns when the extra isn't installed."),
    "logging_utils":    ("Logging configuration and custom handlers",
                         "Drop-in `configure_logging`, level-filtering handlers, an in-memory ring-buffer handler, and an introspection helper "
                         "(`return_method_name`) used throughout the package for self-naming log messages."),
    "safe_paths":       ("Exception-swallowing filesystem queries",
                         "`safe_*` wrappers around `os.stat`/`Path.exists`/`is_file`/`is_dir` that never raise, plus `ensure_file`/`ensure_dir` "
                         "builders that compose on top of them."),
    "file_io":          ("Atomic file-write helper",
                         "`my_atomic_write` — lazy `atomicwrites` + `filelock` wrapper that lets you write text to a path with cross-process safety."),
    "io_subprocess":    ("Subprocess wrappers + critical-error reporter",
                         "`my_fopen` (smart-encoding text-file opener), `my_popen` (subprocess with timeout + capture), `my_critical_error` "
                         "(logging + traceback + raise pattern), and the `MyPopenResult` data carrier."),
    "prompts":          ("Interactive Y/N + multi-choice prompts",
                         "Two small helpers that funnel through `input()` with consistent retry behavior."),
    "introspection":    ("AST + source-code reflection",
                         "Render a function's source with original whitespace, parse module-level constants out of a file, normalize objects "
                         "into dicts, compile source snippets in-memory, and conditionally read-and-eval embedded scripts."),
    "humanize":         ("Human-readable number formatting",
                         "Byte sizes (`1.0 GiB`), scientific-notation exponents, and away-from-zero rounding (lazy numpy)."),
    "datetime_utils":   ("Date / time parsing, formatting, timezone handling",
                         "`parse_datetime` is the load-bearing dispatcher (handles ISO, JD/MJD, decimal years, dateutil fallbacks); "
                         "supplemented by `AdaptiveDateFormatter` for matplotlib, `human_timespan` for durations, and a small zoo of "
                         "tz/JD helpers."),
    "json_io":          ("JSON serialization + dataclass conversion",
                         "`to_jsonable`/`from_jsonable` round-trip recursively-typed structures including `Path`, `datetime`, and dataclasses, "
                         "with paired `save_options_to_json`/`load_options_from_json` helpers for `Options` objects."),
    "diff_view":        ("Diff rendering with visible whitespace",
                         "`my_diff` (color unified diff), `diff_and_confirm` (interactive accept/reject loop), `highlight_changes` (per-line "
                         "intra-word emphasis), and `is_python_script` (the heuristic that decides whether a path holds Python source)."),
    "text":             ("Mojibake fixing, encoding detection, casing helpers",
                         "ftfy-based `fix_text`/`fix_mojibake` (with an atomic write-back), explicit UTF-8 / CP-1252 decoders, sentence-aware "
                         "`my_capitalize`/`my_title_case`, and `normalize_for_search` for diacritic-folded comparisons."),
    "hosts":            ("Hostname + computer-name detection",
                         "Five strategies for retrieving a hostname (socket / platform / uname / `hostname` / scutil), aggregated by "
                         "`get_computer_name` with a NASA-prefix detector."),
    "network":          ("Internet-connectivity probes",
                         "`is_internet_available` runs a multi-strategy DNS + HTTP + TCP check against `net_targets` with a captive-portal sniff "
                         "and a shared `ThreadPoolExecutor`."),
    "python_env":       ("Python version + shell-environment detection",
                         "Helpers for picking a Python interpreter, locating the user's shell rc file, and finding alias-source files."),
    "files":            ("Checksums, downloads, filename formatting, free-space queries",
                         "`download_file` with progress, `calculate_checksum`, `query_free_space` via shutil, `filename_format` for legal-on-most-OSes "
                         "name munging, and `verify_script` to confirm a shell script is well-formed."),
    "lint":             ("flake8 / autopep8 / mypy interactive runners + multireplace",
                         "Run linters, gather + display findings with color, prompt-and-apply autopep8 fixes, and the `multireplace` regex-driven "
                         "search-and-replace tool that shares lint internals."),
    "treeview":         ("Directory tree with new-file highlighting",
                         "Renders a colored ASCII tree starting at a directory, marking files newer than a cutoff."),
    "docker_utils":     ("Docker daemon + image lifecycle helpers",
                         "Ensure the docker daemon is running, the requested image is built, and rerun a command with auto-fixes when daemon "
                         "or image is missing."),
    "system":           ("OS-level process + resource helpers",
                         "`kill_process`, `is_process_running`, `start_only_one_instance` (PID-lock idempotency), `detect_country` (IP geoloc), "
                         "and file-manager / terminal-launcher entry points."),
    "media":            ("Video / audio helpers (ffmpeg, VLC, system volume)",
                         "Open paths in VLC, find the bundled ffmpeg, query video duration, slice + concatenate video segments, and set the "
                         "system volume via pulsectl."),
    "html_files":       ("HTML filename munging + multi-file combination",
                         "Strip a leading prefix from filenames or `<title>` tags, and concatenate multiple HTML files into one."),
    "llm":              ("LLM wrapper, config dataclasses, model selection",
                         "The 2 000-LOC `LLMs` class wraps `litellm`/`tiktoken` with `LLMConfig`/`ModelInfo` dataclasses, a `SelectionStrategy` enum, "
                         "and lazy backoff via tenacity."),
}


# -------- render policy -------- #

GITHUB_BASE: Final[str] = "https://github.com/killett/emmykit/blob/main"


@dataclasses.dataclass(frozen=True)
class CondenseGroup:
    """A family of related constants collapsed into one TOC + body entry."""

    label: str         # Human-readable label; doubles as anchor text and TOC entry.
    names: list[str]   # Symbols absorbed into this group; first present name's source_line drives the link.
    summary: str       # Short body line shown inside the <details> body.


@dataclasses.dataclass(frozen=True)
class ModuleRenderRule:
    """Per-module render directives consumed by build_readme.

    Names listed in both `omit` and a `condense.names` list are treated as an
    authoring error — keep them in only one place.
    """

    omit: list[str] = dataclasses.field(default_factory=list)
    condense: list[CondenseGroup] = dataclasses.field(default_factory=list)
    section_note: str | None = None    # Appended to the module's intro paragraph.
    drop_section: bool = False         # Skip the whole section in TOC + body.


_EXT_NAMES: Final[tuple[str, ...]] = (
    "ALL_KNOWN_EXTENSIONS", "ARCHIVE_EXTENSIONS", "AUDIO_EXTENSIONS",
    "BOOK_EXTENSIONS", "HTML_EXTENSIONS", "IMAGE_EXTENSIONS",
    "PLAYLIST_EXTENSIONS", "PYTHON_EXTENSIONS", "SUBTITLE_EXTENSIONS",
    "TEXT_ENCODINGS", "TEXT_EXTENSIONS", "VIDEO_EXTENSIONS",
)


RENDER_RULES: dict[str, ModuleRenderRule] = {
    "constants": ModuleRenderRule(
        omit=["BACKTICK", "EM_DASH", "HORIZONTAL_ELLIPSIS",
              "LDQUOTE", "LSQUOTE", "RDQUOTE", "RSQUOTE"],
        condense=[
            CondenseGroup(
                label="ANSI color escapes",
                names=["ANSI_CYAN", "ANSI_GREEN", "ANSI_RED", "ANSI_RESET", "ANSI_YELLOW"],
                summary="5 terminal-escape strings: ANSI_CYAN / GREEN / RED / RESET / YELLOW.",
            ),
            CondenseGroup(
                label="IGNORED_CODES",
                names=["IGNORED_CODES"],
                summary="flake8 + autopep8 codes Emmy deliberately ignores.",
            ),
            CondenseGroup(
                label="IGNORE_THESE_ERRORS",
                names=["IGNORE_THESE_ERRORS"],
                summary="errno codes treated as benign by safe_* helpers.",
            ),
        ],
    ),
    "extensions": ModuleRenderRule(
        omit=[n + "_SET" for n in _EXT_NAMES],
        section_note=(
            "Each `*_EXTENSIONS` list has a `*_EXTENSIONS_SET` frozenset alias "
            "for fast membership tests."
        ),
    ),
    "datetime_utils": ModuleRenderRule(omit=["ADAPTIVE_FORMAT_LEVELS"]),
    "embedded_scripts": ModuleRenderRule(
        section_note=(
            "The five standalone command-line programs that used to live here "
            "(`PRINTALL_SCRIPT`, `MYDIFF_SCRIPT`, `MYAUDIT_SCRIPT`, "
            "`MULTIREPLACE_SCRIPT`, `TREEVIEW_SCRIPT`) moved to "
            "[killett/utilities](https://github.com/killett/utilities) in 0.4.0; "
            "`UNIV_DEFS_SYS_PATH_SCRIPT` was deleted."
        ),
    ),
    "hosts": ModuleRenderRule(
        condense=[CondenseGroup(
            label="NASA computer-name prefixes",
            names=["NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES", "NASA_COMPUTER_NAME_PREFIXES"],
            summary="Prefix lists feeding `IS_NASA_COMPUTER` detection.",
        )],
    ),
    "net_targets": ModuleRenderRule(drop_section=True),
    "text_constants": ModuleRenderRule(drop_section=True),
}


# When a module is `drop_section=True`, prepend its substance to the named
# downstream module's section intro.
SECTION_DROP_NOTES: dict[str, tuple[str, str]] = {
    "net_targets": (
        "network",
        "Probe targets live in `emmykit.net_targets` "
        "(`IPV4_TARGETS` / `IPV6_TARGETS` / `HTTP_PROBES` / `DNS_TEST_NAMES`) "
        "and feed `is_internet_available`.",
    ),
    "text_constants": (
        "text",
        "Translation tables live in `emmykit.text_constants` "
        "(`CHARACTERS_TO_SPACE` / `QUOTES_TO_DELETE` / `REPLACE_WITH_SPACE` / `TRANSLATION_TABLE`) "
        "and feed `normalize_for_search`.",
    ),
}


def _slug(label: str) -> str:
    """Lowercase + non-alnum runs → hyphens; stable across runs."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


# -------- introspection -------- #


@dataclasses.dataclass
class SymbolInfo:
    name: str
    module: str
    kind: str  # "function" | "class" | "var" | "annvar"
    summary: str
    signature: str | None
    docstring: str | None
    value_preview: str | None
    annotation: str | None
    method_names: list[str] | None
    dataclass_field_names: list[str] | None
    source_line: int


def _read_module_source(module: str) -> tuple[str, list[str], ast.Module, dict[str, ast.AST]]:
    """Return (raw_text, line_list, parsed_ast, top_level_name_to_node)."""
    path = SRC_DIR / f"{module}.py"
    text = path.read_text()
    lines = text.splitlines()
    tree = ast.parse(text)
    name_to_node: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name_to_node[node.name] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name_to_node[node.target.id] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    name_to_node[t.id] = node
                elif isinstance(t, ast.Tuple):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            name_to_node[e.id] = node
    return text, lines, tree, name_to_node


def _inline_comment_for_lineno(text: str, lineno: int) -> str | None:
    """Return the inline `#` comment that appears on or just after the assignment at lineno.

    For single-line assignments the comment is on the same line. For multi-line annotated
    assignments (e.g. a list literal spanning many lines) the leading inline comment, if any,
    sits at the end of the first line of the assignment.
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenizeError:
        return None
    for tok in toks:
        if tok.type == tokenize.COMMENT and tok.start[0] == lineno:
            return tok.string.lstrip("#").strip()
    return None


def _value_preview(obj: Any, *, max_chars: int = 200, name: str = "") -> str:
    """Repr the object, truncated; multi-line containers get pprint.

    Embedded-script strings (anything in the embedded_scripts module) are summarized
    by length rather than content — their bodies contain historical `univ_defs`
    references that distract from the README's purpose.
    """
    if isinstance(obj, str) and name.endswith("_SCRIPT") and len(obj) > 200:
        n_lines = obj.count("\n") + 1
        return f"'<{len(obj):,}-char Python script source, {n_lines} lines>'"
    if isinstance(obj, (set, frozenset)):
        # Set ordering varies across processes (hash randomization) — sort for determinism.
        try:
            ordered = sorted(obj, key=lambda x: (str(type(x).__name__), repr(x)))
        except TypeError:
            ordered = sorted(obj, key=repr)
        body = ", ".join(repr(x) for x in ordered)
        prefix, suffix = ("frozenset({", "})") if isinstance(obj, frozenset) else ("{", "}")
        full = f"{prefix}{body}{suffix}"
        if len(full) > max_chars:
            full = full[: max_chars - 4] + "..."
        return full
    if isinstance(obj, (list, tuple, dict)) and len(obj) > 3:
        pretty = pprint.pformat(obj, width=88, compact=True)
        if len(pretty) > max_chars:
            head = pretty[: max_chars - 5].rsplit(",", 1)[0]
            return f"{head}, ...{pretty[-1]}"
        return pretty
    r = repr(obj)
    if len(r) > max_chars:
        return r[: max_chars - 4] + "..."
    return r


def _synthesize_const_summary(name: str, obj: Any, annotation: str | None) -> str:
    """Fallback summary line when the constant has no inline comment."""
    if isinstance(obj, str) and len(obj) <= 60:
        return f"{annotation or 'str'} = {obj!r}"
    if isinstance(obj, str):
        return f"{annotation or 'str'} ({len(obj)} chars)"
    if isinstance(obj, (int, float, bool)) and not isinstance(obj, bool) is False:
        return f"{annotation or type(obj).__name__} = {obj!r}"
    if annotation:
        if isinstance(obj, (list, tuple, set, frozenset)):
            return f"{annotation} ({len(obj)} items)"
        if isinstance(obj, dict):
            return f"{annotation} ({len(obj)} entries)"
        return annotation
    cls = type(obj).__name__
    if isinstance(obj, (list, tuple, set, frozenset)):
        return f"{cls} ({len(obj)} items)"
    if isinstance(obj, dict):
        return f"{cls} ({len(obj)} entries)"
    return cls


def _first_docstring_line(doc: str | None) -> str:
    if not doc:
        return ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _truncate_summary(text: str, max_chars: int = 120) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _gather(module: str, names: list[str], emmykit: Any) -> list[SymbolInfo]:
    text, lines, tree, name_to_node = _read_module_source(module)
    out: list[SymbolInfo] = []
    for name in sorted(names, key=lambda s: s.lower()):
        obj = getattr(emmykit, name)
        node = name_to_node.get(name)
        if node is None:
            # Should never happen — layout drift.
            continue

        if inspect.isfunction(obj):
            sig = str(inspect.signature(obj))
            doc = inspect.getdoc(obj)
            summary = _truncate_summary(_first_docstring_line(doc)) or "(no docstring)"
            out.append(SymbolInfo(
                name=name, module=module, kind="function",
                summary=summary, signature=f"{name}{sig}", docstring=doc,
                value_preview=None, annotation=None,
                method_names=None, dataclass_field_names=None,
                source_line=node.lineno,
            ))
        elif inspect.isclass(obj):
            doc = inspect.getdoc(obj)
            summary = _truncate_summary(_first_docstring_line(doc)) or "(no docstring)"
            fields = None
            if dataclasses.is_dataclass(obj):
                fields = [f.name for f in dataclasses.fields(obj)]
            # For dataclasses with > 6 fields the __init__ signature is a giant blob
            # that can drag historical default values (paths, etc.) into the README;
            # show the field list instead, which is more useful for readers anyway.
            if fields is not None and len(fields) > 6:
                sig_text: str | None = None
            else:
                try:
                    sig_text = f"{name}{inspect.signature(obj)}"
                except (TypeError, ValueError):
                    sig_text = f"{name}(...)"
            methods = sorted(
                m for m in dir(obj)
                if not m.startswith("_") and callable(getattr(obj, m, None))
            )
            out.append(SymbolInfo(
                name=name, module=module, kind="class",
                summary=summary, signature=sig_text, docstring=doc,
                value_preview=None, annotation=None,
                method_names=methods or None,
                dataclass_field_names=fields,
                source_line=node.lineno,
            ))
        else:
            # Constant / annotated var.
            annotation = None
            if isinstance(node, ast.AnnAssign) and node.annotation is not None:
                annotation = ast.unparse(node.annotation)
            inline = _inline_comment_for_lineno(text, node.lineno)
            summary = inline or _synthesize_const_summary(name, obj, annotation)
            preview = _value_preview(obj, name=name)
            out.append(SymbolInfo(
                name=name, module=module, kind="annvar" if isinstance(node, ast.AnnAssign) else "var",
                summary=_truncate_summary(summary),
                signature=None, docstring=None,
                value_preview=preview, annotation=annotation,
                method_names=None, dataclass_field_names=None,
                source_line=node.lineno,
            ))
    return out


# -------- rendering -------- #


def _render_symbol(s: SymbolInfo) -> str:
    parts: list[str] = []
    parts.append(f'<a id="{s.name.lower()}"></a>')
    parts.append("<details>")
    parts.append(f"<summary><code>{s.name}</code> — {s.summary}</summary>")
    parts.append("")
    if s.kind in ("function", "class"):
        if s.signature is not None:
            parts.append("```python")
            parts.append(s.signature)
            parts.append("```")
        if s.docstring:
            parts.append("")
            parts.append("```text")
            parts.append(s.docstring.rstrip())
            parts.append("```")
        if s.kind == "class" and s.dataclass_field_names:
            parts.append("")
            parts.append("**Fields:** " + ", ".join(f"`{f}`" for f in s.dataclass_field_names) + ".")
        if s.kind == "class" and s.method_names:
            parts.append("")
            parts.append("**Public methods:** " + ", ".join(f"`{m}`" for m in s.method_names) + ".")
    else:
        # Constant
        decl = f"{s.name}"
        if s.annotation:
            decl += f": {s.annotation}"
        decl += f" = {s.value_preview}"
        parts.append("```python")
        parts.append(decl)
        parts.append("```")
    parts.append("")
    parts.append(f"[source ↗]({GITHUB_BASE}/src/emmykit/{s.module}.py#L{s.source_line})")
    parts.append("")
    parts.append("</details>")
    parts.append("")
    return "\n".join(parts)


def _render_condense_group(module: str, group: "CondenseGroup", source_line: int, present_names: list[str]) -> str:
    """Render a CondenseGroup as one <details> block, replacing the per-symbol blocks.

    The source link points at `source_line` (the first present name's location).
    """
    slug = _slug(group.label)
    parts: list[str] = []
    parts.append(f'<a id="c-{module}-{slug}"></a>')
    parts.append("<details>")
    parts.append(f"<summary><code>{group.label}</code> — {group.summary}</summary>")
    parts.append("")
    parts.append("**Includes:** " + ", ".join(f"`{n}`" for n in present_names) + ".")
    parts.append("")
    parts.append(f"[source ↗]({GITHUB_BASE}/src/emmykit/{module}.py#L{source_line})")
    parts.append("")
    parts.append("</details>")
    parts.append("")
    return "\n".join(parts)


def _render_group(
    module: str,
    layer: int,
    symbols: list[SymbolInfo],
    condense_blocks: list[tuple["CondenseGroup", int, list[str]]] | None = None,
    extra_notes: list[str] | None = None,
) -> str:
    subtitle, intro = MODULE_DESCRIPTIONS[module]
    chunks: list[str] = []
    # `m-` prefix on module anchors avoids collision with same-case-folded symbol names
    # (e.g. `options` module vs `Options` class).
    chunks.append(f'<a id="m-{module}"></a>')
    chunks.append(f"### `{module}` — {subtitle}")
    chunks.append("")
    chunks.append(f"_Layer {layer}._  `from emmykit.{module} import …`")
    chunks.append("")
    chunks.append(intro)
    if extra_notes:
        for note in extra_notes:
            chunks.append("")
            chunks.append(note)
    chunks.append("")
    for s in symbols:
        chunks.append(_render_symbol(s))
    if condense_blocks:
        for group, source_line, present_names in condense_blocks:
            chunks.append(_render_condense_group(module, group, source_line, present_names))
    return "\n".join(chunks)


def _render_toc(groups: list[tuple[int, str, list[SymbolInfo], list[tuple["CondenseGroup", int, list[str]]]]]) -> str:
    out: list[str] = []
    out.append("## Table of contents")
    out.append("")
    for _, module, symbols, condense_blocks in groups:
        subtitle, _ = MODULE_DESCRIPTIONS[module]
        out.append(f"- [`{module}` — {subtitle}](#m-{module})")
        for s in symbols:
            out.append(f"  - [`{s.name}`](#{s.name.lower()})")
        for group, _src_line, _present in condense_blocks:
            slug = _slug(group.label)
            out.append(f"  - [`{group.label}`](#c-{module}-{slug})")
    out.append("")
    return "\n".join(out)


HEADER = """# emmykit

Personal Python utility kit: 181 importable functions, classes, and constants across 32 submodules
in 9 dependency layers (README highlights the user-facing surface — internal punctuation, frozenset
aliases, probe-target lists, and translation tables are referenced by section rather than enumerated).
Base install is stdlib-only; heavier helpers
(datetime parsing via numpy/pandas/dateutil, mojibake fixing via ftfy, lint runners,
LLM wrappers, ffmpeg/VLC controls) are gated behind optional extras so a bare
`import emmykit` is fast and side-effect-free.

## Install

```bash
pip install emmykit                 # base — stdlib only
pip install 'emmykit[all]'          # all optional extras
pip install 'emmykit[datetime]'     # pick a single extra group
```

```bash
uv add emmykit                      # base
uv add 'emmykit[all]'               # all optional extras
uv add 'emmykit[datetime]'          # pick a single extra group
```

Available extras groups: `datetime`, `text`, `lint`, `llm`, `media`, `files`, `inflection`, `html`, `all`.

## Quick start

```python
import emmykit as ek

print(ek.human_bytesize(1024**3))        # "1.0 GiB"
ts = ek.parse_datetime("2026-06-06T12:34:56Z")
print(ek.my_capitalize("hello world"))   # "Hello world"
```

## Teaching the JSON round trip about your own types

`to_jsonable` / `from_jsonable` know a fixed set of types (`Path`, `set`,
`datetime`, `Decimal`, `Enum`, compiled regexes, …). Anything else falls through
to `str(obj)`, which fails *silently*: the file reloads holding a repr string
where an object should be, and membership tests quietly degrade to substring
matching. Register your types instead — `emmykit` never has to import your
package.

```python
import emmykit as ek

class Duration:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Duration) and other.seconds == self.seconds

ek.register_json_type(
    Duration,
    lambda o: {"seconds": o.seconds},          # -> payload
    tag="duration",                            # -> written as "__type__"
    decode=lambda p: Duration(p["seconds"]),   # payload -> object
)

blob = ek.to_jsonable({"limit": Duration(90)})
# {"limit": {"__type__": "duration", "seconds": 90}}
ek.from_jsonable(blob) == {"limit": Duration(90)}   # True
```

This also reaches `save_options_to_json` / `load_options_from_json`, which call
the converters internally.

- **Dispatch is by `isinstance`**, so subclasses are covered. When two
  registrations match, the more specific class wins; unrelated ties go to the
  most recently registered.
- **Registrations beat the built-ins.** A registered handler is consulted before
  every built-in encoder and before the `str()` fallback.
- **Payloads are converted too.** The mapping your encoder returns is passed back
  through the converter, so it may contain `Path`, `set`, `datetime`, or another
  registered type. The recursion guard stays in effect across that call.
- **`roundtrip=False`** returns the bare payload with no `__type__` key.
- **Encode-only registration** — omit *both* `tag` and `decode` (supplying one
  without the other is an error). The object is serialized through its encoder
  but never tagged, in either `roundtrip` mode, and reloads as a plain `dict`:

  ```python
  ek.register_json_type(LiveIndex, lambda o: {"probed": sorted(o.names), "offline": o.offline})
  ```

  This is the honest choice for an object that can be *described* faithfully but
  not *rebuilt* faithfully — one whose contents came from probing a live
  interpreter or a live HTTP client, where a reconstructed copy would answer
  differently while looking identical. A readable snapshot plus a plain `dict` on
  reload beats a decoder that fabricates a plausible-but-wrong object.
- **Tags are exclusive.** Reusing a registered tag or class raises unless you
  pass `replace=True`; the built-in tags in `BUILTIN_JSON_TAGS` (`path`, `set`,
  `datetime`, `recursion`, …) are rejected outright. `unregister_json_type(cls)`
  or `unregister_json_type("tag")` removes a handler again — useful in test
  teardown.

"""

FOOTER = """## License

Apache 2.0 — see [LICENSE](LICENSE). Changelog at [CHANGELOG.md](CHANGELOG.md).
"""


_EXTRA_NOTES_BY_MODULE: dict[str, list[str]] = {}


def build_readme() -> str:
    sys.path.insert(0, str(SRC_DIR.parent))
    import emmykit  # noqa: WPS433

    public = [n for n in emmykit.__all__ if n not in STDLIB_REEXPORTS]

    layout = json.loads(LAYOUT_PATH.read_text())
    sym_to_mod = {s: m for m, syms in layout.items() for s in syms}
    by_mod: dict[str, list[str]] = {}
    for name in public:
        mod = sym_to_mod.get(name)
        if mod is None:
            continue
        by_mod.setdefault(mod, []).append(name)

    # Pre-compute notes flowing INTO each module from dropped sections.
    notes_into: dict[str, list[str]] = {}
    for src_mod, (dst_mod, note) in SECTION_DROP_NOTES.items():
        notes_into.setdefault(dst_mod, []).append(note)

    groups: list[tuple[int, str, list[SymbolInfo], list[tuple[CondenseGroup, int, list[str]]]]] = []
    for layer, module in LAYER_ORDER:
        rule = RENDER_RULES.get(module, ModuleRenderRule())
        if rule.drop_section:
            continue
        names = by_mod.get(module, [])
        if not names:
            continue
        omit_set = set(rule.omit)
        absorbed = {n for g in rule.condense for n in g.names}
        individual_names = [n for n in names if n not in omit_set and n not in absorbed]
        gathered = _gather(module, individual_names, emmykit)
        condense_blocks: list[tuple[CondenseGroup, int, list[str]]] = []
        for g in rule.condense:
            present = [n for n in g.names if n in names]
            if not present:
                continue
            first_info = _gather(module, [present[0]], emmykit)
            if not first_info:
                continue
            condense_blocks.append((g, first_info[0].source_line, present))
        # Module render: optional section_note + any inflowing drop-section notes.
        extra_notes: list[str] = []
        if rule.section_note:
            extra_notes.append(rule.section_note)
        extra_notes.extend(notes_into.get(module, []))
        groups.append((layer, module, gathered, condense_blocks))
        # Stash extra_notes on the tuple for _render_group; use a parallel dict
        # to keep tuple shape compatible with _render_toc.
        _EXTRA_NOTES_BY_MODULE[module] = extra_notes

    toc = _render_toc(groups)
    body = "\n".join(
        _render_group(m, l, s, c, _EXTRA_NOTES_BY_MODULE.get(m))
        for l, m, s, c in groups
    )

    return HEADER + toc + "\n## API reference\n\n" + body + "\n" + FOOTER


def main(argv: list[str]) -> int:
    args = set(argv[1:])
    text = build_readme()
    if "--stdout" in args:
        sys.stdout.write(text)
        return 0
    if "--check" in args:
        current = README_PATH.read_text() if README_PATH.exists() else ""
        if current != text:
            sys.stderr.write("README.md is stale — re-run tools/generate_readme.py\n")
            return 1
        sys.stderr.write("README.md is up-to-date\n")
        return 0
    README_PATH.write_text(text)
    sys.stderr.write(f"wrote {README_PATH} ({len(text.splitlines())} lines)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
