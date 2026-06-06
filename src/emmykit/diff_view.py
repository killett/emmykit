"""diff_view — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import re

from emmykit.constants import (
    ANSI_CYAN, ANSI_GREEN, ANSI_RED, ANSI_RESET, ANSI_YELLOW, DEFAULT_ENCODING,
)
from emmykit.extensions import PYTHON_EXTENSIONS_SET
from emmykit.logging_utils import fallback_logging_config, return_method_name
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import ensure_file, safe_is_file, safe_stat
from emmykit.io_subprocess import my_fopen
from emmykit.introspection import compile_code


def _vis_trailing_ws(line: str) -> str:
    """
    Replace only the trailing spaces and tabs in 'line'
    with visible glyphs (· for space, → for tab).
    """
    core = line.rstrip(" \t")
    trail = line[len(core):]
    return core + trail.replace(" ", "·").replace("\t", "→")

def _vis_all_ws(s: str) -> str:
    """
    Show *all* spaces/tabs in s as visible glyphs:
      · for space, → for tab
    """
    return s.replace(" ", "·").replace("\t", "→")

def highlight_changes(orig: str, new: str, unchanged_color: str,
                      added_color: str, deleted_color: str) -> tuple[str, str]:
    """
    Compare 'orig' and 'new' strings and return a tuple
    (old_highlighted, new_highlighted), where:
    - old_highlighted has parts present only in 'orig' wrapped in deleted_color.
    - new_highlighted has parts present only in 'new' wrapped in added_color
      and unchanged parts in unchanged_color.

    Args:
        orig:            The original string.
        new:             The modified string.
        unchanged_color: The color to use for unchanged parts.
        added_color:     The color to use for added parts.
        deleted_color:   The color to use for deleted parts.

    Returns:
        A tuple of (old_highlighted, new_highlighted) strings.

    Raises:
        None.
    """
    import difflib
    sm = difflib.SequenceMatcher(None, orig, new)
    new_out: list[str] = []
    old_out: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_segment = orig[i1:i2]
        new_segment =  new[j1:j2]
        if tag == "equal":
            new_out.append(f"{unchanged_color}{new_segment}{ANSI_RESET}")
            old_out.append(old_segment)
        elif tag == "replace":  # segments changed: mark old text as deleted, new text as added
            new_out.append(f"{added_color}{new_segment}{ANSI_RESET}")
            old_out.append(f"{deleted_color}{old_segment}{ANSI_RESET}")
        elif tag == "delete":  # text removed: mark in old, nothing in new
            old_out.append(f"{deleted_color}{old_segment}{ANSI_RESET}")
        elif tag == "insert":  # text added: mark in new, nothing in old
            # text added: if it's *only* whitespace, render it visibly
            if set(new_segment) <= {" ", "\t"}:
                visible = _vis_all_ws(new_segment)
            else:
                visible = new_segment
            new_out.append(f"{added_color}{visible}{ANSI_RESET}")
    return "".join(old_out), "".join(new_out)

def my_diff(orig_text:     str, changed_text: str,
            orig_path:     str | os.PathLike[str],
            changed_path:  str | os.PathLike[str] | None = None,
            diff_choice:   int = 1,
            changed_color: str = ANSI_CYAN,
            deleted_color: str = ANSI_RED,
            added_color:   str = ANSI_YELLOW) -> None:
    """
    Show a diff between 'orig_text' and 'changed_text' in the console,
    highlighting character-level changes within changed lines.

    Args:
        orig_text:      Original text to compare against.
        changed_text:   Proposed changes to the original text.
        orig_path:      Path to the original file.
        changed_path:   Optional path to the changed file (if different).
        diff_choice:    How many context lines to show in the diff ( 0 = old-style diff, 1 = unified diff with 0 context lines,
                                                                    2+ = unified diff with 'diff_choice - 1' context lines).
        changed_color:  Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
        deleted_color:  Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
        added_color:    Color to use for the added characters in changed lines (default ANSI_RED).

    Returns:
        None: Prints the diff to the console.

    Raises:
        None.
    """
    import difflib
    fallback_logging_config(rawlog=True)
    orig_path = ensure_path(orig_path)
    if not changed_path:
        changed_path = orig_path
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("At the top of the function %s(), diff_choice=%s", return_method_name(), diff_choice)
    orig_lines    =    orig_text.splitlines(keepends=True)
    changed_lines = changed_text.splitlines(keepends=True)
    the_digits    = max(len(str(len(orig_lines))), len(str(len(changed_lines))))
    last_removed  = None  # there is no last removed line initially
    # shared buffer for the current hunk's deletes/inserts
    hunk_entries: list[tuple[str, str, int | None, int | None]] = []
    # each entry is (tag, text, orig_lineno, new_lineno)
    # orig_lineno or new_lineno will be None for pure inserts/deletes.

    def process_hunk() -> None:
        """Pair up deletes and inserts in the current hunk and print them with highlights."""
        nonlocal hunk_entries
        if not hunk_entries:
            return
        # Partition current hunk entries.
        deletes = [e for e in hunk_entries if e[0] == "-"]
        inserts = [e for e in hunk_entries if e[0] == "+"]
        # We'll pair in order: kth delete with kth insert.
        pair_count = min(len(deletes), len(inserts))
        di = 0
        # Track which 'new' line numbers have already been consumed by a pairing
        # (so we can skip printing those '+' entries when the loop hits them later).
        consumed_new_line_numbers: set[int] = set()
        for tag, text, dln, nln in hunk_entries:
            if tag == "-":
                if di < pair_count:
                    # Compare this delete with its paired insert.
                    old_vis = _vis_trailing_ws(text)
                    new_text = inserts[di][1]
                    new_nln  = inserts[di][3]
                    new_vis  = _vis_trailing_ws(new_text)
                    # Prove to mypy we're inside a hunk (line numbers present)
                    assert dln is not None and new_nln is not None, "Line numbers should be set in a hunk (dln, new_nln)"
                    # Mark the paired '+' as consumed, regardless of identical/different.
                    consumed_new_line_numbers.add(new_nln)
                    # If identical after visibility transform, emit nothing (no context).
                    if old_vis == new_vis:
                        di += 1
                        continue
                    # Otherwise, highlight differences.
                    old_hl, new_hl = highlight_changes(old_vis, new_vis,
                                                       unchanged_color=changed_color,
                                                       added_color=added_color,
                                                       deleted_color=deleted_color)
                    logging.info(f"< {dln:>{the_digits}}: {old_hl}{ANSI_RESET}")
                    logging.info(f"{changed_color}> {new_nln:>{the_digits}}:{ANSI_RESET} {new_hl}{ANSI_RESET}")
                    di += 1
                else:
                    # Unpaired delete (pure removal in this hunk).
                    logging.info(f"< {dln:>{the_digits}}: {deleted_color}{_vis_trailing_ws(text)}{ANSI_RESET}")
            elif tag == "+":
                # If this '+' was already paired (even if identical), skip it.
                if nln in consumed_new_line_numbers:
                    continue
                # Unpaired insert (pure addition in this hunk).
                vis = _vis_trailing_ws(text)
                logging.info(f"{changed_color}> {nln:>{the_digits}}:{ANSI_RESET} {ANSI_RED}{vis}{ANSI_RESET}")
        hunk_entries.clear()

    def flush_removed(orig_lineno: int) -> None:
        """Flush the last removed line if it exists."""
        nonlocal last_removed
        if last_removed is not None:
            highlighted_old = f"{deleted_color}{last_removed}{ANSI_RESET}"
            logging.info(f"< {orig_lineno:>{the_digits}}: {highlighted_old}")
            last_removed = None

    orig_lineno: int | None = None
    new_lineno:  int | None = None
    if diff_choice == 0:  # old style diff (difflib.Differ)
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Using old-style diff for %s with %d original and %d fixed lines.", os.fspath(orig_path), len(orig_lines), len(changed_lines))
        orig_lineno = 1
        new_lineno  = 1
        for line in difflib.Differ().compare(orig_lines, changed_lines):
            tag, body = line[:2], line[2:].rstrip("\n")
            if tag == "  ":    # context line
                # end of any previous mini‑hunk
                process_hunk()
                flush_removed(orig_lineno)
                orig_lineno += 1
                new_lineno  += 1
            elif tag == "- ":  # original line
                # buffer a delete
                hunk_entries.append(("-", body, orig_lineno, None))
                orig_lineno += 1
            elif tag == "+ ":  # fixed line
                # buffer an insert
                hunk_entries.append(("+", body, None, new_lineno))
                new_lineno += 1
            # skip '? ' lines entirely
        # flush any trailing buffered pairs/inserts
        process_hunk()
        flush_removed(orig_lineno)
    elif diff_choice >= 1:  # unified or context diff
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Using unified diff for %s with %d original and %d fixed lines.", os.fspath(orig_path), len(orig_lines), len(changed_lines))
        ctx  = max(diff_choice - 1, 0)
        diff = difflib.unified_diff(
            orig_lines, changed_lines,
            fromfile=os.fspath(orig_path), tofile=os.fspath(changed_path),
            n=ctx, lineterm=""
        )
        header_re:   re.Pattern = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
        for line in diff:
            if line.startswith("@@"):  # hunk header?
                # flush any leftover from the prior hunk
                process_hunk()
                m = header_re.match(line)
                if not m:
                    logging.error("Failed to parse hunk header line: %s", line)
                    continue
                orig_lineno = int(m.group(1))
                new_lineno  = int(m.group(2))
                continue
            if line.startswith(("---", "+++")):  # skip file header lines
                continue
            tag, body = line[0], line[1:].rstrip("\n")
            if tag == " ":  # context line: flush and emit
                process_hunk()
                if orig_lineno is not None:
                    flush_removed(orig_lineno)
                assert orig_lineno is not None and new_lineno is not None, "Line numbers should be set in a hunk (orig_lineno, new_lineno)"
                logging.info(f"  {orig_lineno:>{the_digits}}: {_vis_trailing_ws(body)}")
                orig_lineno += 1
                new_lineno  += 1
            elif tag == "-":  # buffer a delete
                hunk_entries.append(("-", body, orig_lineno, None))
                assert orig_lineno is not None, "Line numbers should be set in a hunk (orig_lineno)"
                orig_lineno += 1
            elif tag == "+":  # buffer an insert
                hunk_entries.append(("+", body, None, new_lineno))
                assert new_lineno is not None, "Line numbers should be set in a hunk (new_lineno)"
                new_lineno += 1
        # final flush
        process_hunk()
        if orig_lineno is not None:
            flush_removed(orig_lineno)
    else:
        logging.error("Unsupported diff_choice = %d. Must be a non-negative integer.", diff_choice)

def is_python_script(path: str | os.PathLike[str]) -> bool:
    """
    Return True if 'path' looks like a Python script:
      1. It's a file which ends in .py or .pyw
      2. Or it is executable AND its first line is a python shebang

    Args:
        path: The file path to check.

    Returns:
        True if the path is a Python script, False otherwise.

    Raises:
        IsADirectoryError: If the path is a directory.
        FileNotFoundError: If the file is not found.
        PermissionError:   If the file is not accessible due to permission issues.
    """
    path = ensure_path(path)
    if not safe_is_file(path):
        return False

    # Common extensions
    if path.suffix.casefold() in PYTHON_EXTENSIONS_SET:
        return True

    # No-extension scripts: check for executable bit + python shebang
    try:
        st = safe_stat(path)
    except OSError:
        return False

    if st is None:  # This can happen if the user doesn't have permission to stat the file.
        return False

    # Must be a regular file and executable by owner/group/other
    import stat
    if not stat.S_ISREG(st.st_mode) or not (st.st_mode & (stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)):
        return False

    # Try to read the first line and look for a python shebang
    first_line = my_fopen(path, suppress_errors=True, rawlog=False, numlines=1)
    if not first_line:
        return False
    return bool(re.match(r'#!.*\bpython[0-9.]*\b', first_line))

def diff_and_confirm(orig_text: str, changed_text: str,
                     path: str | os.PathLike[str], label: str = "",
                     skip_compile: bool = False, diff_choice: int = 1,
                     changed_color: str = ANSI_CYAN,
                     deleted_color: str = ANSI_RED,
                     added_color:   str = ANSI_YELLOW,
                     the_fix:       str = "", description: str = "") -> bool:
    """
    Show a unified diff of orig_text → changed_text with a number of context lines
    (determined by 'diff_choice') around each hunk, log using 'label' and 'description', then prompt.
    If the user confirms, overwrite 'path' with changed_text and return True.
    If the user chooses to quit, log a message and return False.

    Args:
        orig_text:     Original text to compare against.
        changed_text:  Proposed changes to the original text.
        path:          Path to the file being modified.
        label:         A short label for the issue being fixed (default "").
        skip_compile:  If True, do not try to compile the changed text before writing (default False).
        diff_choice:   How many context lines to show in the diff (0 = old-style diff, 1 = unified diff with 0 context lines, 2+ = unified diff with 'diff_choice - 1' context lines) (default 1).
        changed_color: Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
        deleted_color: Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
        added_color:   Color to use for the added characters in changed lines (default ANSI_GREEN).
        the_fix:       A string describing the fix being applied (e.g. "autopep8", "manual edit") (default "").
        description:   A longer description of the issue being fixed (default "").

    Returns:
        False if the user chose to quit; True otherwise.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the specified path is not a file. The function which raises this exception is my_fopen().
    """
    fallback_logging_config()
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("At the top of the function %s(), diff_choice=%s", return_method_name(), diff_choice)
    path = ensure_file(path)
    my_diff(orig_text, changed_text, path, diff_choice=diff_choice,
            changed_color=changed_color, deleted_color=deleted_color, added_color=added_color)
    label_str = f"{ANSI_RED}{label}{ANSI_RESET}" if label     else ""
    fix_str   = f" using {the_fix}"              if the_fix   else ""
    subject   = f"{label_str} "                  if label_str else ""
    logging.info("End of proposed %schanges to %s%s.", subject, os.fspath(path), fix_str)
    if description:
        prefix = f"{label_str}: "                if label_str else ""
        logging.info(f"{prefix}{ANSI_YELLOW}{description}{ANSI_RESET}")
    ans = input("Apply these changes? [y/N/q] ").strip().casefold()
    if ans in ("y", "yes"):
        # If the user hasn't chosen to skip compilation and this is a Python script,
        # try to compile the changed text before writing it. If compilation fails, abort the write.
        if not skip_compile and is_python_script(path) and not compile_code(changed_text, force_source=True):
            logging.error(f"{ANSI_RED}Failed to compile the changed python script. Aborting write.{ANSI_RESET}")
            return False  # Don't write if it won't compile, and don't continue.
        path.write_text(changed_text, encoding=DEFAULT_ENCODING)
        if the_fix:
            logging.info(f"{ANSI_GREEN}Applied {the_fix} to {os.fspath(path)}{ANSI_RESET}")
        else:
            logging.info(f"{ANSI_GREEN}Applied changes to {os.fspath(path)}{ANSI_RESET}")
    elif "q" in ans or "exit" in ans:
        logging.info(f"{ANSI_YELLOW}Exiting without further changes.{ANSI_RESET}")
        return False
    else:
        logging.info(f"{ANSI_YELLOW}Skipped writing changes.{ANSI_RESET}")
    return True
