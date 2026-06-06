"""constants — extracted from univ_defs.py."""

from __future__ import annotations

import errno
from typing import Final

DEFAULT_ENCODING: str = "utf-8"

ANSI_RED:    str = "\033[91m"

ANSI_GREEN:  str = "\033[92m"  # this is bold/bright green on Linux but orange on my Mac

ANSI_YELLOW: str = "\033[93m"

ANSI_CYAN:   str = "\033[94m"  # this is blue on Linux but cyan on my Mac

ANSI_RESET:  str = "\033[0m"

IGNORED_CODES: list[str] = [
    "W503",  # line break before binary operator                   (W503 and W504 are mutually exclusive, so ignore both)
    "W504",  # line break  after binary operator                   (W503 and W504 are mutually exclusive, so ignore both)
    "E117",  # over-indented line (comment)                        (I like to play with indentation so this cramps my style)
    "E127",  # continuation line over-indented for visual indent   (I like to play with indentation so this cramps my style)
    "E122",  # continuation line missing indentation or outdented  (I like to play with indentation so this cramps my style)
    "E128",  # continuation line under-indented for visual indent  (I like to play with indentation so this cramps my style)
    "E201",  # whitespace after "("                                (I like to play with white space so this cramps my style)
    "E202",  # whitespace before ")"                               (I like to play with white space so this cramps my style)
    "E203",  # whitespace before ":"                               (I like to play with white space so this cramps my style)
    "E211",  # whitespace before "("                               (I like to play with white space so this cramps my style)
    "E221",  # multiple spaces before operator                     (I like to play with white space so this cramps my style)
    "E222",  # multiple spaces after  operator                     (I like to play with white space so this cramps my style)
    "E226",  # missing whitespace around arithmetic operator       (the fix doesn't work on the right side even with --aggressive)
    "E227",  # missing whitespace around bitwise or shift operator (the fix doesn't work on the right side even with --aggressive)
    "E241",  # multiple spaces after ","                           (I like to play with white space so this cramps my style)
    "E251",  # unexpected spaces around keyword / parameter equals (I like to play with white space so this cramps my style)
    "E262",  # inline comment should start with "# "               (*shrug* I don't wanna)
    "E271",  # multiple spaces  after keyword                      (I like to play with white space so this cramps my style)
    "E272",  # multiple spaces before keyword                      (I like to play with white space so this cramps my style)
    "E701",  # multiple statements on one line (colon)             (I like to group commands together: this cramps my style)
    "E702",  # multiple statements on one line (semicolon)         (I like to group commands together: this cramps my style)
]

BACKTICK            = "\u0060"  # U+0060 "GRAVE ACCENT" (the backtick)

LSQUOTE             = "\u2018"  # U+2018 "LEFT  SINGLE QUOTATION MARK" (curly apostrophe)

RSQUOTE             = "\u2019"  # U+2019 "RIGHT SINGLE QUOTATION MARK" (curly apostrophe)

LDQUOTE             = "\u201C"  # U+201C "LEFT  DOUBLE QUOTATION MARK"

RDQUOTE             = "\u201D"  # U+201D "RIGHT DOUBLE QUOTATION MARK"

HORIZONTAL_ELLIPSIS = "\u2026"  # U+2026 "HORIZONTAL ELLIPSIS" (three closely spaced periods)

EM_DASH             = "\u2014"  # U+2014 "EM DASH"

IGNORE_THESE_ERRORS: Final[frozenset[int]] = frozenset(
    e for e in {
        errno.EACCES, errno.EPERM, errno.ELOOP, errno.ENOTDIR, errno.ENOENT,
        getattr(errno, "ESTALE", None),   # NFS: stale file handle (may not exist)
    } if e is not None
)

DEFAULT_EXCLUDE_DIRS: set[str] = {".git", "__pycache__", ".venv", "venv", "build", "dist"}
