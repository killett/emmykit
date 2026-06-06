"""treeview — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os
from typing import Any

from emmykit.constants import ANSI_CYAN, ANSI_RESET, DEFAULT_ENCODING
from emmykit.logging_utils import fallback_logging_config
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import safe_exists, safe_is_dir, safe_is_file, safe_mtime


def treeview_new_files(directory:      str | os.PathLike[str],
                       last_file_path: str | os.PathLike[str] | None = None,
                       last_mtime: float | None = None, maxlines: int = 0,
                       use_colors: bool = True, print_root: bool = True,
                       prefix: str = "", is_last: bool = True, level: int = 0,
                       state: dict[str, Any] | None = None, probe_only: bool = False) -> bool:
    """
    Recursively scan the directory, print the contents of files newer than last_file_path (if provided- if so store its modification date in last_mtime). Return True if any relevant files are found.

    Args:
        directory:      The directory to scan.
        last_file_path: The optional path to a chosen file. Only files newer than this will be printed.
        last_mtime:     The modification time of the last_file_path. If None, all files will be
                        considered.
        maxlines:       The maximum number of lines to read from each file. 0 means don't read at all,
                        -1 means read all lines, otherwise read up to maxlines (default 0).
        use_colors:     Whether to use ANSI color codes in the output (default True).
        print_root:     If True, print the root directory name (default True).
        prefix:         The prefix to use for logging output (default '').
        is_last:        Whether this is the last item in the current level (default True).
        level:          The current recursion level (default 0).
        state:          A dictionary to maintain state across recursive calls (default None).
        probe_only:     If True, do not print file contents, just check for existence of relevant
                        files (default False).

    Returns:
        True if any relevant files are found or the directory itself is newer than last_mtime,
        False otherwise.

    Raises:
        None: Catches exceptions, logs an error and returns False if the directory is not a valid
              directory or does not exist.
    """
    import datetime as dt
    fallback_logging_config(rawlog=True)

    directory = ensure_path(directory)
    if not safe_exists(directory):
        logging.error(f"{prefix}└── [Directory does not exist: {os.fspath(directory)}]")
        return False
    if not safe_is_dir(directory):
        logging.error(f"{prefix}└── [Not a directory: {os.fspath(directory)}]")
        return False

    if last_file_path is None:
        last_mtime = 0
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%sNo last file path provided, considering all files.", prefix)
    else:
        last_file_path = ensure_path(last_file_path)
        if not safe_exists(last_file_path):
            logging.error("%s└── [Last file path does not exist: %s]", prefix, os.fspath(last_file_path))
            return False
        last_mtime          = safe_mtime(last_file_path)
        if last_mtime is None:
            logging.error("%s└── [Could not get mtime for last file path: %s]",
                          prefix, os.fspath(last_file_path))
            return False
        last_mtime_readable = dt.datetime.fromtimestamp(last_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%sLast file path: %s (mtime: %s)",
                                                                          prefix,
                                                                          os.fspath(last_file_path), last_mtime_readable)

    if use_colors:
        reset_color = ANSI_RESET
        dir_color   = ANSI_CYAN
    else:
        reset_color = ""
        dir_color   = ""

    # Get the modification time of the directory itself
    dir_mtime      = safe_mtime(directory)
    lm: float      = 0.0 if last_mtime is None else last_mtime
    current_is_new = (dir_mtime is not None) and (dir_mtime > lm)

    if state is None:
        state = {"excluded_dirs"   : {"__pycache__"},
                 "already_printed" : set(),
                 "my_filepath"     : ensure_path(__file__)}
    already_printed = state['already_printed']
    excluded_dirs   = state['excluded_dirs']
    my_filepath     = state['my_filepath']

    if not probe_only:
        already_printed.add(directory)

    has_relevant_files = False  # Flag to indicate if current directory has relevant files

    try:
        entries = sorted(directory.iterdir(), key=lambda e: e.name.casefold())
    except PermissionError:
        logging.error(f"{prefix}└── [Permission Denied]")
        return False

    # Filter out entries that should be skipped at the directory level
    entries = [
        entry for entry in entries
        if not (
            (safe_is_file(entry) and (
                entry == last_file_path or
                entry == my_filepath    or
                entry.name.startswith(".")
            )) or
            ((safe_is_dir_entry := safe_is_dir(entry)) and entry.name in excluded_dirs) or
            (safe_is_dir_entry and entry.expanduser().resolve() in already_printed)
        )
    ]

    # Sort entries: directories first, then files, case-insensitive
    entries = sorted(entries, key=lambda e: (not safe_is_dir(e), e.name.casefold()))

    # Collect relevant entries
    relevant_entries = []
    subdirectories = []

    for entry in entries:
        if safe_is_file(entry):
            file_mtime = safe_mtime(entry)
            if file_mtime and file_mtime > last_mtime:
                relevant_entries.append(entry)
                has_relevant_files = True
        elif safe_is_dir(entry):
            sub_has_relevant = treeview_new_files(
                entry,
                last_file_path=last_file_path,
                last_mtime=last_mtime,
                maxlines=maxlines,
                use_colors=use_colors,      # use_colors doesn't matter in probe mode
                prefix=prefix,              # prefix doesn't matter in probe mode
                is_last=False,              # ignored in probe mode
                level=level + 1,
                state=state,
                probe_only=True             # probe mode: do not print contents
            )
            # Consider the subdirectory's own mtime
            sub_is_new = (smt := safe_mtime(entry)) is not None and smt > last_mtime
            if sub_has_relevant or sub_is_new:
                subdirectories.append(entry)
            if sub_has_relevant:
                has_relevant_files = True

    # Sort subdirectories and relevant entries by name, case-insensitive
    subdirectories.sort(  key=lambda p: p.name.casefold())
    relevant_entries.sort(key=lambda p: p.name.casefold())

    should_show = has_relevant_files or current_is_new
    if probe_only:
        return should_show

    if should_show:
        if level > 0:
            # Print the directory name with a connector only if it's not the root directory
            connector = "└── " if is_last else "├── "
            logging.info(f"{prefix}{connector}{dir_color}{directory.name}/{reset_color}")

            # Update the prefix for child entries
            child_prefix = prefix + ("    " if is_last else "│   ")
        else:
            # For root level, do not print the directory name unless print_root is True
            child_prefix = prefix
            if print_root:
                # Print the root directory name with a connector
                logging.info(f"{dir_color}{directory.name}/{reset_color}")

        # Print subdirectories first
        printable_subdirs = [
            d for d in subdirectories
            if d.name not in excluded_dirs and d.expanduser().resolve() not in already_printed
        ]
        for i, subdir in enumerate(printable_subdirs):
            is_sub_last = (i == len(printable_subdirs) - 1) and (len(relevant_entries) == 0)
            # Only scan the subdirectory if it isn't excluded
            if subdir.name not in excluded_dirs and subdir.expanduser().resolve() not in already_printed:
                treeview_new_files(subdir, last_file_path=last_file_path, last_mtime=last_mtime,
                                   maxlines=maxlines, use_colors=use_colors, prefix=child_prefix,
                                   is_last=is_sub_last, level=level + 1, state=state)

        # Print relevant files next
        for i, file_entry in enumerate(relevant_entries):
            # Determine if this is the last file to adjust connector
            is_file_last = (i == len(relevant_entries) - 1)
            file_connector = "└── " if is_file_last else "├── "
            contents_str = f"{file_entry.name} contents:" if maxlines != 0 else f"{file_entry.name}"
            logging.info(f"{child_prefix}{file_connector}{contents_str}")
            try:
                if maxlines != 0:  # Only open if not disabled
                    with open(file_entry, "r", encoding=DEFAULT_ENCODING) as f:
                        if maxlines > 0:
                            # Read only up to maxlines
                            lines = []
                            for i, line in enumerate(f):
                                if i >= maxlines:
                                    break
                                lines.append(line.rstrip("\n"))
                        else:  # maxlines == -1 → read all
                            lines = [line.rstrip("\n") for line in f]
                    # Indent file contents for better readability
                    indented_contents = "\n".join(f"{child_prefix}    {line}" for line in lines)
                    logging.info(indented_contents)
            except Exception:  # Catch any unexpected errors from reading the file without crashing.
                logging.exception(f"{child_prefix}    Error reading '{file_entry}'.")
            if maxlines != 0:  # Add an empty line for separation, but only if printing contents
                logging.info("")

    return should_show
