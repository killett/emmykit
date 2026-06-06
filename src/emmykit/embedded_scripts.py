"""embedded_scripts — extracted from univ_defs.py."""

from __future__ import annotations

from pathlib import Path

UNIV_DEFS_SYS_PATH_SCRIPT: str = f'''# Auto-generated helper: ensure the univ_defs directory is on sys.path
import sys
from pathlib import Path

univ_defs_dir = Path({str(Path(__file__).parent.resolve())!r}).resolve()
if not univ_defs_dir.is_dir():
    raise FileNotFoundError(f"Expected univ_defs_dir to be a directory: {{univ_defs_dir}}")
if str(univ_defs_dir) not in sys.path:
    sys.path.append(str(univ_defs_dir))
'''

MYDIFF_SCRIPT: str = r'''from __future__ import annotations
import os
import sys
import argparse
import logging
from pathlib import Path
import univ_defs_sys_path_script  # Appends sys.path with the location of univ_defs.py
import univ_defs as ud

__version__: str = "0.1.0"


class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the Options class with default values."""
        self.my_name:  str = Path(sys.argv[0]).stem  # The invoked name of this script without the .py extension
        self.log_mode: int = logging.INFO  # Use the -debug command line argument to change to DEBUG.
        self.args: argparse.Namespace = argparse.Namespace()
        self.default_dir: Path = Path.cwd().expanduser().resolve(strict=True)  # Default to current working directory


def parse_arguments(options: Options) -> None:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Diff two files using ud.my_diff().")
    parser.add_argument("orig_path", type=Path, help="Path to original file.")
    parser.add_argument("changed_path", type=Path, help="Path to changed file.")
    parser.add_argument("--diff_choice", type=int, default=1,
                        help="0 = old-style diff, 1 = unified diff with 0 context lines, "
                             "2+ = unified diff with 'diff_choice - 1' context lines")
    parser.add_argument("--changed_color", type=str, default=ud.ANSI_CYAN,
                        help="Color for unchanged characters in changed lines (default: ANSI_CYAN)")
    parser.add_argument("--deleted_color", type=str, default=ud.ANSI_RED,
                        help="Color for deleted characters in original lines (default: ANSI_RED)")
    parser.add_argument("--added_color", type=str, default=ud.ANSI_GREEN,
                        help="Color for added characters in changed lines (default: ANSI_GREEN)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-debug", "--debug", action="store_true",
                        help="Enable DEBUG logging.")
    options.args = parser.parse_args()
    if options.args.debug:
        options.log_mode = logging.DEBUG


def main() -> None:
    """Main function."""
    options: Options = Options()
    parse_arguments(options)
    memory_handler = ud.configure_logging(options.my_name, log_level=options.log_mode,
                                          rawlog=True)
    orig_text    = ud.my_fopen(options.args.orig_path)
    changed_text = ud.my_fopen(options.args.changed_path)
    if orig_text is False:
        logging.error(f"Failed to read original file: {os.fspath(options.args.orig_path)}")
        return
    if changed_text is False:
        logging.error(f"Failed to read changed file: {os.fspath(options.args.changed_path)}")
        return
    if orig_text == changed_text:
        return  # Standard diff would show no changes
    ud.my_diff(orig_text, changed_text, options.args.orig_path,
               changed_path=options.args.changed_path, diff_choice=options.args.diff_choice,
               changed_color=options.args.changed_color, deleted_color=options.args.deleted_color,
               added_color=options.args.added_color)
    ud.print_all_errors(memory_handler)
    logging.shutdown()


if __name__ == "__main__":
    main()
'''

MYAUDIT_SCRIPT: str = r'''from __future__ import annotations
import sys
import argparse
import logging
from pathlib import Path

import univ_defs_sys_path_script  # Appends sys.path with the location of univ_defs.py
import univ_defs as ud

__version__: str = "0.1.0"


class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the Options class with default values."""
        self.my_name:  str = Path(sys.argv[0]).stem  # The invoked name of this script without the .py extension
        self.log_mode: int = logging.INFO  # Use the -debug command line argument to change to DEBUG.
        self.args: argparse.Namespace = argparse.Namespace()
        self.default_dir: Path = Path.cwd().expanduser().resolve(strict=True)  # Default to current working directory


def parse_arguments(options: Options) -> None:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Check Python formatting in a file.")
    parser.add_argument("filepath", type=Path, help="Path to the Python file to check")
    parser.add_argument("--diff_choice", type=int, default=1,
                        help="0 = old-style diff, 1 = unified diff with 0 context lines, "
                             "2+ = unified diff with 'diff_choice - 1' context lines")
    parser.add_argument("--changed_color", type=str, default=ud.ANSI_CYAN,
                        help="Color for unchanged characters in changed lines (default: ANSI_CYAN)")
    parser.add_argument("--deleted_color", type=str, default=ud.ANSI_RED,
                        help="Color for deleted characters in original lines (default: ANSI_RED)")
    parser.add_argument("--added_color", type=str, default=ud.ANSI_GREEN,
                        help="Color for added characters in changed lines (default: ANSI_GREEN)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-debug", "--debug", action="store_true",
                        help="Enable DEBUG logging.")
    options.args = parser.parse_args()
    if options.args.debug:
        options.log_mode = logging.DEBUG


def main() -> None:
    """Main function."""
    options: Options = Options()
    parse_arguments(options)
    memory_handler = ud.configure_logging(options.my_name, log_level=options.log_mode,
                                          rawlog=True)
    if not ud.check_python_formatting(options.args.filepath, diff_choice=options.args.diff_choice):
        return
    ud.interactive_flake8(options, options.args.filepath, diff_choice=options.args.diff_choice,
                          ignore_codes=ud.IGNORED_CODES, max_line_length=1000,
                          changed_color=options.args.changed_color, deleted_color=options.args.deleted_color,
                          added_color=options.args.added_color)
    ud.run_mypy(options, options.args.filepath)
    ud.print_all_errors(memory_handler)
    logging.shutdown()


if __name__ == "__main__":
    main()
'''

MULTIREPLACE_SCRIPT: str = r'''from __future__ import annotations
import sys
import argparse
import logging
from pathlib import Path

import univ_defs_sys_path_script  # Appends sys.path with the location of univ_defs.py
import univ_defs as ud

__version__: str = "0.1.0"


class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the Options class with default values."""
        self.my_name:  str = Path(sys.argv[0]).stem  # The invoked name of this script without the .py extension
        self.log_mode: int = logging.INFO  # Use the -debug command line argument to change to DEBUG.
        self.args: argparse.Namespace = argparse.Namespace()
        self.default_glob_pattern: str = "*"
        self.default_dir: Path = Path.cwd().expanduser().resolve(strict=True)  # Default to current working directory


def parse_arguments(options: Options) -> None:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Find files by glob and call ud.ask_and_replace() on each until it returns False.")
    parser.add_argument("old_str",
                        help="The text to be replaced in the files.")
    parser.add_argument("new_str",
                        help="The text to replace the old_str.")
    parser.add_argument("glob_pattern", nargs="?", default=options.default_glob_pattern, metavar="GLOB",
                        help=f'Glob pattern of files to edit (default: "{options.default_glob_pattern}"). Example: "*.py"')
    parser.add_argument("--dir", "-d", type=Path, default=options.default_dir, metavar="DIR",
                        help=f"Directory to search in (defaults to current working directory: {options.default_dir}).")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Search recursively in subdirectories.")
    parser.add_argument("--verbose", "-V", action="store_true",
                        help="Log messages about files with no occurrences found.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-debug", "--debug", action="store_true",
                        help="Enable DEBUG logging.")
    options.args = parser.parse_args()
    if options.args.debug:
        options.log_mode = logging.DEBUG


def main() -> None:
    """Main function."""
    options: Options = Options()
    parse_arguments(options)
    memory_handler = ud.configure_logging(options.my_name, log_level=options.log_mode,
                                          rawlog=True)
    ud.multireplace(options, verbose=options.args.verbose)
    ud.print_all_errors(memory_handler)
    logging.shutdown()


if __name__ == "__main__":
    main()
'''

TREEVIEW_SCRIPT: str = r'''#!/usr/bin/env python3
from __future__ import annotations

import sys
import argparse
import logging
from pathlib import Path

import univ_defs_sys_path_script  # Appends sys.path with the location of univ_defs.py
import univ_defs as ud

__version__: str = "0.1.1"


class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the Options class with default values."""
        self.my_name:                    str = Path(sys.argv[0]).stem  # The invoked name of this script without the .py extension
        self.default_exclude_dirs:  set[str] = set(ud.DEFAULT_EXCLUDE_DIRS)
        self.default_dir:               Path = Path.cwd().expanduser().resolve(strict=True)  # Default to current working directory
        self.log_mode:                   int = logging.INFO  # Use the -debug command line argument to change to DEBUG.
        self.args: argparse.Namespace = argparse.Namespace()


def parse_arguments(options: Options) -> None:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Print a tree view of the specified directory.")
    parser.add_argument("directory", type=Path, nargs="?", default=options.default_dir,
                        help=f"Directory to search in (defaults to current working directory: {options.default_dir}).")
    parser.add_argument("--no-colors", action="store_true",
                        help="Do not use colors in the output.")
    parser.add_argument("--exclude-dirs", action="extend", nargs="+", default=None,
                        help=f"Directory name to exclude (can be given multiple times). Any directories given will be added to the default set: {sorted(options.default_exclude_dirs)}")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-debug", "--debug", action="store_true",
                        help="Enable DEBUG logging.")
    options.args = parser.parse_args()
    options.args.exclude_dirs = set(ud.DEFAULT_EXCLUDE_DIRS) | set(options.args.exclude_dirs or [])
    if options.args.debug:
        options.log_mode = logging.DEBUG


def main() -> None:
    """Main function."""
    options: Options = Options()
    parse_arguments(options)
    memory_handler = ud.configure_logging(options.my_name, log_level=options.log_mode,
                                          rawlog=True)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Directory: %s", options.args.directory)
    state = {
        "excluded_dirs"   : options.args.exclude_dirs,
        "already_printed" : set(),
        "my_filepath"     : Path(__file__).expanduser().resolve(),
    }
    ud.treeview_new_files(options.args.directory, use_colors=not options.args.no_colors, state=state)
    ud.print_all_errors(memory_handler)
    logging.shutdown()


if __name__ == "__main__":
    main()
'''

PRINTALL_SCRIPT: str = r'''from __future__ import annotations

import os
import sys
import argparse
import io
import logging
import re
from pathlib import Path
from collections.abc import Iterable

import tokenize  # stdlib

import univ_defs_sys_path_script  # Appends sys.path with the location of univ_defs.py
import univ_defs as ud

__version__: str = "0.1.1"


class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the Options class with default values."""
        self.my_name:                    str = Path(sys.argv[0]).stem  # The invoked name of this script without the extension
        self.default_exclude_dirs:  set[str] = set(ud.DEFAULT_EXCLUDE_DIRS)
        self.log_mode:                   int = logging.INFO  # Use -debug to change to logging.DEBUG.
        self.args: argparse.Namespace = argparse.Namespace()


def parse_arguments(options: Options) -> None:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Search Python files and print full logical statements that match a pattern.")
    parser.add_argument("paths", nargs="+", type=Path,  # parse as Path at the boundary
                        help="Files and/or directories to search.")
    parser.add_argument("-p", "--pattern", required=True, help="Search pattern (string or regex).")
    parser.add_argument("-E", "--regex", action="store_true",
                        help="Treat the pattern as a regular expression.")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive match.")
    parser.add_argument("-n", "--line-numbers", action="store_true",
                        help="Show line numbers in output blocks.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recurse into directories.")
    parser.add_argument("--no-glob", action="store_true",
                        help="Do not automatically filter for *.py inside directories.")
    parser.add_argument("--exclude-dirs", action="extend", nargs="+", default=None,
                        help=f"Directory name to exclude (can be given multiple times). Any directories given will be added to the default set: {sorted(options.default_exclude_dirs)}")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-debug", "--debug", action="store_true", help="Enable debug logging.")
    options.args = parser.parse_args()
    options.args.exclude_dirs = set(ud.DEFAULT_EXCLUDE_DIRS) | set(options.args.exclude_dirs or [])
    if options.args.debug:
        options.log_mode = logging.DEBUG


def _is_excluded(path: Path, excluded: set[str]) -> bool:
    """Return True if any ancestor directory name is in the excluded set."""
    # Only compare directory names (Path.name); do not do string-prefix checks.
    return any(parent.name in excluded for parent in path.parents)


def iter_files(paths: Iterable[str | os.PathLike[str]],
               recursive: bool,
               excluded: set[str],
               only_py: bool) -> Iterable[Path]:
    """
    Yield files from given paths, respecting recursion and directory excludes.

    Parameters that represent paths accept str | os.PathLike[str] at the boundary.
    Returned paths are pathlib.Path instances.
    """
    pattern = "*.py" if only_py else "*"

    for raw in paths:
        base = Path(raw)

        if ud.safe_is_dir(base):
            if recursive:
                # Prefer Path.rglob for recursion (portable across 3.9+).
                for f in base.rglob(pattern):
                    if ud.safe_is_file(f) and not _is_excluded(f, excluded):
                        yield f
            else:
                for f in base.glob(pattern):
                    if ud.safe_is_file(f) and not _is_excluded(f, excluded):
                        yield f
        else:
            # Single file (or non-existent); yield if it meets filters.
            if ud.safe_is_file(base) and (not only_py or base.suffix == ".py") and not _is_excluded(base, excluded):
                yield base


def _statement_spans(src: str) -> list[tuple[int, int]]:
    """Return list of (start_line, end_line) for each logical statement in the source."""
    reader = io.StringIO(src).readline
    spans: list[tuple[int, int]] = []
    depth = 0
    start_line: int | None = None

    for tok in tokenize.generate_tokens(reader):
        tok_type, tok_str, start, end, _ = tok

        # establish start at first meaningful token of a statement
        if start_line is None and tok_type not in (tokenize.NL, tokenize.COMMENT,
                                                   tokenize.INDENT, tokenize.DEDENT,
                                                   tokenize.ENDMARKER):
            start_line = start[0]

        if tok_type == tokenize.OP:
            if tok_str in "([{":
                depth += 1
            elif tok_str in ")]}":
                depth -= 1
            elif tok_str == ";" and depth == 0 and start_line is not None:
                spans.append((start_line, start[0]))
                start_line = None
                continue

        if tok_type == tokenize.NEWLINE and depth == 0:
            if start_line is not None:
                spans.append((start_line, end[0]))
            start_line = None

        if tok_type == tokenize.ENDMARKER:
            break

    return spans


def _mask_strings_and_comments(src: str) -> str:
    """Return source with STRING and COMMENT contents replaced by spaces (preserving positions)."""
    lines = src.splitlines(keepends=True)
    matrix = [list(line) for line in lines]
    reader = io.StringIO(src).readline
    for tok in tokenize.generate_tokens(reader):
        tok_type, _tok_str, start, end, _ = tok
        if tok_type in (tokenize.STRING, tokenize.COMMENT):
            (sr, sc), (er, ec) = start, end
            # mask all full lines covered by the token
            for r in range(sr - 1, er - 1):
                cstart = sc if r == sr - 1 else 0
                for c in range(cstart, len(matrix[r])):
                    if matrix[r][c] != "\n":
                        matrix[r][c] = " "
            # final line (partial)
            r = er - 1
            if 0 <= r < len(matrix):
                cstart = 0 if sr != er else sc
                for c in range(cstart, ec):
                    if matrix[r][c] != "\n":
                        matrix[r][c] = " "
    return "".join("".join(row) for row in matrix)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent spans."""
    if not spans:
        return []
    spans = sorted(spans)
    merged: list[list[int]] = [[spans[0][0], spans[0][1]]]
    for s, e in spans[1:]:
        last = merged[-1]
        if s <= last[1] + 1:
            last[1] = max(last[1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _extract_blocks(src: str, spans: list[tuple[int, int]], show_line_numbers: bool) -> list[str]:
    """Return pretty-printed blocks for each span."""
    lines = src.splitlines()
    if show_line_numbers:
        max_line = max((e for _, e in spans), default=0)
        width = len(str(max_line))
    blocks: list[str] = []
    for s, e in spans:
        segment = lines[s - 1:e]
        if show_line_numbers:
            segment = [f"{i:>{width}} | {line}" for i, line in zip(range(s, e + 1), segment)]
        blocks.append("\n".join(segment))
    return blocks


def search_file(path: str | os.PathLike[str],
                pattern: str, *,
                regex: bool,
                ignore_case: bool,
                show_line_numbers: bool) -> list[str]:
    """Return matching blocks for a single file."""
    p    = ud.ensure_file(path)
    text = ud.my_fopen(p, suppress_errors=True)
    if not isinstance(text, str):
        logging.warning("Skipping %s (unreadable or non-text).", os.fspath(p))
        return []

    masked = _mask_strings_and_comments(text)
    flags  = re.IGNORECASE if ignore_case else 0
    pat    = re.compile(pattern if regex else re.escape(pattern), flags)

    # lines that contain a match (in code, not in strings/comments)
    hit_lines: set[int] = set()
    for m in pat.finditer(masked):
        before = masked[:m.start()]
        line = before.count("\n") + 1
        hit_lines.add(line)

    if not hit_lines:
        return []

    # map lines to statement spans
    spans = _statement_spans(text)
    line_to_span: dict[int, tuple[int, int]] = {}
    for s, e in spans:
        for ln in range(s, e + 1):
            line_to_span[ln] = (s, e)

    chosen: list[tuple[int, int]] = []
    for ln in sorted(hit_lines):
        sp = line_to_span.get(ln)
        if sp:
            chosen.append(sp)

    chosen = _merge_spans(chosen)
    return _extract_blocks(text, chosen, show_line_numbers)


def main() -> None:
    """
    Main function.
    """
    options: Options = Options()
    parse_arguments(options)
    logging.basicConfig(level=options.log_mode,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    any_hits = False

    for file in iter_files(options.args.paths, options.args.recursive,
                           options.args.exclude_dirs, only_py=not options.args.no_glob):
        results = search_file(file, options.args.pattern, regex=options.args.regex,
                              ignore_case=options.args.ignore_case,
                              show_line_numbers=options.args.line_numbers)
        if results:
            any_hits = True
            print(f"# {os.fspath(file)}")
            for block in results:
                print(block)
                print()  # extra newline between blocks

    if not any_hits:
        logging.info("No matches found.")

    logging.shutdown()


if __name__ == "__main__":
    main()
'''

SETUP_CARTOPY_SCRIPT: str = r'''import os
import matplotlib.pyplot as plt
import cartopy
cartopy.config["data_dir"] = os.getenv("CARTOPY_DATA_DIR", cartopy.config.get("data_dir"))

fig, ax = plt.subplots(subplot_kw={"projection": cartopy.crs.PlateCarree()})
# Explicitly specify resolution and add the ocean and land features to ensure pre-loading
ax.coastlines("110m")
ax.add_feature(cartopy.feature.OCEAN)
ax.add_feature(cartopy.feature.LAND)

# Force feature download
temp_filename = "cartopy_test_map.png"
plt.savefig(temp_filename)
os.remove(  temp_filename)
'''
