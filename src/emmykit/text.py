"""text — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import re

from emmykit.extensions import HTML_EXTENSIONS_SET
from emmykit.logging_utils import fallback_logging_config
from emmykit.text_constants import TRANSLATION_TABLE
from emmykit.file_io import my_atomic_write
from emmykit.safe_paths import ensure_file, safe_is_file
from emmykit.diff_view import my_diff

from typing import Type

def my_capitalize(string_to_capitalize: str) -> str:
    """Capitalize ONLY the first letter of a string and DON'T modify the rest of it."""
    if not string_to_capitalize:
        return ""
    return string_to_capitalize[0].upper() + string_to_capitalize[1:]

def my_title_case(the_title: str) -> str:
    """Capitalize the first letter of each word, but if a word already has ANY uppercase letters, leave it as is. This way, words like "WW2" or "iZombie" won't be modified."""
    words = the_title.split()
    capitalized_words = [word if any(letter.isupper() for letter in word)
                         else word.title() for word in words]
    return " ".join(capitalized_words)

def decode_utf8(raw_bytes: bytes, path_str: str = "input string") -> str | None:
    """
    If the file at 'path' is valid UTF-8 without lone C1 controls,
    return the decoded string. Otherwise, return None.
    """
    fallback_logging_config()
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s failed to decode as UTF‑8.", path_str, exc_info=True)
        return None
    if any(0x0080 <= ord(ch) <= 0x009F for ch in text):
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s contains lone C1 controls, not valid UTF-8.", path_str)
        return None
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s decoded as valid UTF‑8.", path_str)
    return text

def decode_cp1252(raw_bytes: bytes, path_str: str = "input string") -> str | None:
    """
    Attempt to decode CP1252 bytes and return as a string.
    If it fails, return None.
    """
    fallback_logging_config()
    try:
        text = raw_bytes.decode("cp1252", errors="strict")
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s decoded as valid CP1252.",
                                                                          path_str)
        return text
    except UnicodeDecodeError:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("%s failed to decode as CP1252.", path_str, exc_info=True)
        return None

def contains_mojibake(text: str) -> bool:
    """Use ftfy.badness.is_bad() to detect any likely mojibake in the text."""
    import ftfy
    fallback_logging_config()
    try:
        mojibake_present = ftfy.badness.is_bad(text)
    except Exception:  # Catch any unexpected errors from ftfy without crashing
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Failed to check for mojibake.", exc_info=True)
        mojibake_present = False
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Mojibake present: %s", mojibake_present)
    # I HAVEN'T TRIED THIS NEXT LINE, BUT IT MIGHT CAUSE FEWER FALSE POSITIVES:
    # return ftfy.badness(text) > 1
    return mojibake_present

def fix_text(current_text: str, path: str | os.PathLike[str], raw_bytes: bytes) -> str | None:
    """
    Fix mojibake in a string using ftfy.fix_encoding().
    """
    import ftfy
    fallback_logging_config()
    path = ensure_file(path)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Checking %s for mojibake.",
                                                                      os.fspath(path))
    if not contains_mojibake(current_text):
        return None
    try:
        fixed = ftfy.fix_encoding(current_text)
    except Exception:  # Catch any unexpected errors from ftfy without crashing
        logging.error("Failed to fix mojibake in %s.", os.fspath(path), exc_info=True)
        return None
    # If logging level is set to DEBUG, show my diff of original vs fixed:
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        try:
            # Mangle the original string to simulate browser encoding issues:
            mangled_original = raw_bytes.decode("cp1252", errors="replace")
            my_diff(mangled_original, fixed, path)
        except Exception:  # Catch any unexpected errors from decoding but don't crash.
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Could not simulate browser mangling in %s.", os.fspath(path), exc_info=True)
    return fixed

def ensure_utf8_meta(html: str) -> str:
    """
    Ensure the HTML text has a <meta charset="utf-8"> tag.
    If one already exists—either as a charset attribute or
    as an http-equiv Content-Type declaration—normalize it to
    <meta charset="utf-8">. Otherwise, insert that tag right
    after the opening <head> tag.
    """
    # 1) Normalize any <meta ... charset=...> to <meta charset="utf-8">
    #    This covers both <meta charset="XYZ"> and
    #    <meta http-equiv="Content-Type" content="text/html; charset=XYZ">
    def _replace_charset_attr(match: re.Match) -> str:
        """
        Replace a <meta> tag with a charset attribute
        with a normalized <meta charset="utf-8"> tag.
        """
        # Always produce exactly: <meta charset="utf-8">
        return '<meta charset="utf-8">'

    # Pattern A: <meta ... charset=XYZ ...>
    pattern_a = r'<meta\b[^>]*\bcharset=["\']?[^"\'>\s]+["\']?[^>]*>'
    # Pattern B: <meta ... http-equiv=["\']Content-Type["\'] ... content="...; charset=XYZ"...>
    pattern_b = (r'<meta\b[^>]*\bhttp-equiv=["\']?Content-Type["\']?[^>]*'
                 r'\bcontent=["\'][^"\'>]*;\s*charset=[^"\'>]+["\'][^>]*>')

    if re.search(pattern_a, html, flags=re.IGNORECASE) or \
       re.search(pattern_b, html, flags=re.IGNORECASE):
        # First collapse any Pattern B occurrences
        html = re.sub(pattern_b, _replace_charset_attr, html, flags=re.IGNORECASE)
        # Then collapse any remaining Pattern A
        html = re.sub(pattern_a, _replace_charset_attr, html, flags=re.IGNORECASE)
        return html

    # 2) If no existing meta‐charset, insert one just after <head>
    return re.sub(r'(<head\b[^>]*>)',
                  r'\1\n    <meta charset="utf-8">',
                  html, count=1, flags=re.IGNORECASE)

def fix_mojibake(filepath: str | os.PathLike[str], make_backup: bool = True,
                 dry_run: bool = False) -> None:
    """
    Fix mojibake in a text file, recoding from CP1252 to UTF-8 if necessary.
    If the file is already valid UTF-8, it will only fix mojibake.
    """
    import datetime as dt
    fallback_logging_config()
    filepath = ensure_file(filepath)
    if not safe_is_file(filepath):
        logging.error(f"{os.fspath(filepath)} is not a file")
        return

    try:
        with open(filepath, "rb") as f:
            raw_bytes = f.read()
    except Exception:  # Catch any unexpected errors from reading the file without crashing.
        logging.error(f"Failed to read {os.fspath(filepath)}.", exc_info=True)
        return

    original_text =      decode_utf8(raw_bytes, os.fspath(filepath)) \
                    or decode_cp1252(raw_bytes, os.fspath(filepath))
    if original_text is None:
        return

    # Start with the original text but keep it in memory unmodified.
    current_text = original_text

    # Either way, check for mojibake and fix it if necessary
    maybe_fixed = fix_text(current_text, filepath, raw_bytes)
    if maybe_fixed is not None:
        current_text = maybe_fixed
        logging.info("✔ Fixed mojibake: %s", os.fspath(filepath))

    # If the text is from an HTML file, ensure it has a UTF-8 meta tag
    if filepath.suffix.casefold() in HTML_EXTENSIONS_SET:
        current_text = ensure_utf8_meta(current_text)

    # If we have fixed the text, write it back
    if current_text != original_text:
        if dry_run:
            logging.info("Dry run: would write changes to %s", os.fspath(filepath))
        else:
            if make_backup:
                current_datetime = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                backup_path_str = f"{os.fspath(filepath)}_{current_datetime}.bak"
                try:
                    filepath.rename(backup_path_str)
                    logging.info("Backup created: %s", backup_path_str)
                except OSError:
                    logging.exception("Failed to create backup for %s.", os.fspath(filepath))
                    return
            my_atomic_write(filepath, current_text, "w", encoding="utf-8")
            logging.info("✔ Successfully fixed mojibake in %s", os.fspath(filepath))

def normalize_for_search(text: str) -> str:
    """Convert text to ASCII and lowercase for case- and diacritic-insensitive comparison. Also treat some characters such as ._- the same as spaces. Remove quotes (', ", ' and their unicode variants)."""
    fallback_logging_config()
    try:
        from unidecode import unidecode
        decoded_text = unidecode(text)
    except ImportError:
        logging.warning("unidecode module not installed; diacritics will not be removed.")
        decoded_text = text
    return decoded_text.casefold().translate(TRANSLATION_TABLE)
