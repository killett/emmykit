"""text_constants — extracted from univ_defs.py."""

from __future__ import annotations

from emmykit.constants import (
    BACKTICK,
    EM_DASH,
    HORIZONTAL_ELLIPSIS,
    LDQUOTE,
    LSQUOTE,
    RDQUOTE,
    RSQUOTE,
)

CHARACTERS_TO_SPACE = f"._-{EM_DASH}{HORIZONTAL_ELLIPSIS}"

REPLACE_WITH_SPACE  = " " * len(CHARACTERS_TO_SPACE)

QUOTES_TO_DELETE  = f"\"'{BACKTICK}{LSQUOTE}{RSQUOTE}{LDQUOTE}{RDQUOTE}"

TRANSLATION_TABLE = str.maketrans(CHARACTERS_TO_SPACE, REPLACE_WITH_SPACE, QUOTES_TO_DELETE)
