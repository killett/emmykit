"""html_files — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os

from emmykit.constants import DEFAULT_ENCODING
from emmykit.extensions import HTML_EXTENSIONS_SET
from emmykit.logging_utils import fallback_logging_config
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import ensure_file, safe_exists, safe_is_file
from emmykit.io_subprocess import my_fopen


def remove_prefix_from_filename(filepath: str | os.PathLike[str], prefix: str) -> bool:
    """
    If the given filepath's base filename starts with the given prefix:
      1. Remove the prefix (and any " _-" immediately following it).
      2. Move the file (but only if that doesn't cause errors).

    Args:
        filepath: The path to the file whose name may need to be changed.
        prefix:   The prefix to remove from the filename.

    Returns:
        True:  If the file was renamed.
        False: If it was not: the name doesn't start with the prefix, nothing would be
               left of it without the prefix, or the new name already exists.

    Raises:
        OSError: If the rename operation fails due to an OS error (e.g., permission denied).
    """
    fallback_logging_config()
    filepath = ensure_path(filepath)
    if not safe_exists(filepath):
        logging.warning("File or directory '%s' does not exist.", os.fspath(filepath))
        return False
    file = filepath.name
    if file.startswith(prefix):
        new_file = file.replace(prefix, "", 1)  # Replace only the first occurrence
        # Drop the separators (" _-") that followed the prefix
        new_file = new_file.lstrip(" _-")
        if not new_file:
            logging.warning("Cannot rename '%s': nothing is left of the name without the prefix '%s'.",
                            os.fspath(filepath), prefix)
            return False
        new_filepath = filepath.parent / new_file
        if not safe_exists(new_filepath):
            try:
                filepath.rename(new_filepath)
                logging.info("Renamed '%s' to '%s'.", os.fspath(filepath), os.fspath(new_filepath))
                return True
            except OSError as e:
                raise OSError(f"Failed to rename '{os.fspath(filepath)}' to '{os.fspath(new_filepath)}': {e}") from e
        else:
            logging.warning("Cannot rename '%s' to '%s': New path already exists.",
                            os.fspath(filepath), os.fspath(new_filepath))
            return False
    else:
        return False

def remove_prefix_from_html_title(filepath: str | os.PathLike[str], prefix: str) -> bool:
    """
    If the given filepath is an HTML file and its title starts with the given prefix, remove the prefix from the title and save the file, then return True. Otherwise, return False.

    The file is written back in the encoding it was read in (UTF-8, else CP1252), so
    it stays consistent with any charset it declares.
    """
    import re
    fallback_logging_config()
    filepath = ensure_path(filepath)
    if not safe_is_file(filepath):
        logging.warning("File '%s' does not exist or is not a file.", os.fspath(filepath))
        return False
    if filepath.suffix.casefold() not in HTML_EXTENSIONS_SET:
        logging.warning("File '%s' is not an HTML or HTM file.", os.fspath(filepath))
        return False
    raw = filepath.read_bytes()
    if not raw:
        logging.warning("File '%s' is empty or could not be read.", os.fspath(filepath))
        return False
    # latin-1 last: it decodes any bytes, so the file always round-trips.
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            html = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    m = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if m is None:
        logging.warning("Could not find the title in the HTML file '%s'.", os.fspath(filepath))
        return False
    title = m.group(1)
    if title.startswith(prefix):
        new_html = html[:m.start(1)] + title[len(prefix):] + html[m.end(1):]
        filepath.write_bytes(new_html.encode(encoding))
        logging.info("Removed prefix '%s' from the title in '%s'.", prefix, os.fspath(filepath))
        return True
    else:
        return False

def combine_html_files(file_paths:  list[str | os.PathLike[str]],
                       output_file_path: str | os.PathLike[str]) -> None:
    """
    Combine multiple HTML files into a single HTML file.
    The first file's <head> is preserved, and all <body> contents are concatenated.

    Args:
        file_paths:       List of (presorted) file paths to the HTML files to combine.
        output_file_path: Path to save the combined HTML file.

    Returns:
        None: the combined HTML is saved to the specified output file path.

    Raises:
        FileNotFoundError: If any of the input files do not exist.
        ImportError:       If BeautifulSoup is not installed.
        OSError:           If the output file or its folder cannot be written.
    """
    from bs4 import BeautifulSoup
    fallback_logging_config()
    combined_body = ""
    head_content  = ""
    first_file_processed = False
    for file_path in file_paths:
        file_path     = ensure_file(file_path)
        file_contents = my_fopen(file_path)
        if not file_contents:
            logging.warning("File '%s' is empty or could not be read; skipping.", os.fspath(file_path))
            continue
        try:
            soup = BeautifulSoup(file_contents, "html.parser")
            # Keep the <head> of the first file only; a file may have none.
            if not first_file_processed:
                head_content = str(soup.head) if soup.head is not None else ""
                first_file_processed = True
            # The body's contents, not the <body> element itself, which would
            # nest inside the new one. A fragment without <body> is used whole.
            if soup.body is not None:
                combined_body += soup.body.decode_contents()
            else:
                if soup.head is not None:
                    soup.head.decompose()
                combined_body += soup.decode_contents()
        except Exception:  # Catch any unexpected errors from BeautifulSoup without crashing.
            logging.exception(f"File {os.fspath(file_path)} encountered an error.")
    # Create the new HTML structure
    combined_html = f"<!DOCTYPE html>\n<html>\n{head_content}\n<body>\n{combined_body}\n</body>\n</html>"
    # Save to the output file path; a failure reaches the caller.
    output_file_path = ensure_path(output_file_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    output_file_path.write_text(combined_html, encoding=DEFAULT_ENCODING)
    logging.info("Saved combined HTML to '%s'.", os.fspath(output_file_path))
