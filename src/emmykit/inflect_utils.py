"""inflect_utils — extracted from univ_defs.py."""

from __future__ import annotations

import logging
from typing import Literal, Protocol

class InflectEngine(Protocol):
    """Protocol for the 'inflect' library's engine interface."""

    def plural_noun(self, word: str, count: int | None = ...) -> str | Literal[False]:
        """Return the plural form of 'word' if count != 1, else False."""
        ...

    def plural(self, word: str) -> str:
        """Return the plural form of 'word'."""
        ...

_INFLECT_ENGINE: InflectEngine | None = None

def _get_inflect_engine() -> InflectEngine:
    """
    Get or create a singleton inflect engine instance. This function exists to
    appease type checkers like mypy and to avoid global import-time dependencies.

    Args:
        None.

    Returns:
        An instance of the inflect engine.

    Raises:
        ImportError: If the 'inflect' library is not installed.
    """
    global _INFLECT_ENGINE
    if _INFLECT_ENGINE is None:
        import inflect  # type: ignore[import-not-found]
        _INFLECT_ENGINE = inflect.engine()  # type: ignore[assignment]
    assert _INFLECT_ENGINE is not None
    return _INFLECT_ENGINE

def my_plural(n: int, word: str) -> str:
    """
    Return a pluralized version of 'word' preceded by 'n'.

    Behavior:
    - If the open-source 'inflect' library is available, use it for pluralization.
    - Otherwise, fall back to a casefold()-based irregulars table, some uncountables,
      and a small set of morphological rules.

    Examples (fallback behavior):
        1 millennium -> "1 millennium"
        2 millennium -> "2 millennia"
        2 millenium  -> "2 millennia"   # (handles the common misspelling too)

    Args:
        n:    The quantity of the item.
        word: The singular form of the item.

    Returns:
        A string in the format "{n} {pluralized_word}".

    Raises:
        None.
    """
    if n == 1:
        return f"{n} {word}"

    # 1) Try the open-source 'inflect' library if present
    try:  # MIT-licensed, widely used for pluralization
        engine = _get_inflect_engine()
        plural = engine.plural_noun(word, n) or engine.plural(word)
        if plural:
            return f"{n} {plural}"
    except Exception as e:
        # Fall through to custom logic if inflect isn't available or errors
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "my_plural: exception checking inflect library: %s", e
        )

    # 2) Fallback: irregular/uncountable lists (case-insensitive via casefold)
    irregulars = {
        # Common irregulars
        "child"      : "children",
        "person"     : "people",
        "man"        : "men",
        "woman"      : "women",
        "mouse"      : "mice",
        "goose"      : "geese",
        "tooth"      : "teeth",
        "foot"       : "feet",
        "ox"         : "oxen",

        # Classical/latin/greek
        "cactus"     : "cacti",
        "focus"      : "foci",
        "fungus"     : "fungi",
        "nucleus"    : "nuclei",
        "syllabus"   : "syllabi",
        "analysis"   : "analyses",
        "diagnosis"  : "diagnoses",
        "thesis"     : "theses",
        "crisis"     : "crises",
        "phenomenon" : "phenomena",
        "criterion"  : "criteria",
        "datum"      : "data",
        "index"      : "indices",
        "appendix"   : "appendices",
        "matrix"     : "matrices",
        "vertex"     : "vertices",
        "radius"     : "radii",
        "alumnus"    : "alumni",
        "alumna"     : "alumnae",
        "bacterium"  : "bacteria",
        "medium"     : "media",
        "millennium" : "millennia",
        "millenium"  : "millennia",  # handle common misspelling

        # Mixed/accepted forms — pick one
        "octopus"    : "octopuses",
        "platypus"   : "platypuses",
        "virus"      : "viruses",
    }

    uncountables = {
        "sheep", "deer", "series", "species", "aircraft", "moose",
        "bison", "swine", "offspring", "spacecraft", "elk", "reindeer",
        "caribou", "antelope", "quail", "grouse", "cod", "herring",
        "mackerel", "halibut", "bass", "swordfish", "catfish", "bluefish",
        "shellfish", "krill", "means", "headquarters", "barracks", "corps",
        "crossroads", "hovercraft", "watercraft"
    }

    def _preserve_simple_case(src: str, target: str) -> str:
        """Match ALLCAPS or Titlecase of 'src' onto 'target'."""
        if src.isupper():
            return target.upper()
        if src.istitle():
            # Capitalize first letter only; keeps internal case of target
            return target[:1].upper() + target[1:]
        return target

    def _basic_rules(w: str) -> str:
        """Very small set of English pluralization rules."""
        lw = w.casefold()
        # Endings that usually take 'es'
        if lw.endswith(("s", "ss", "sh", "ch", "x", "z")):
            return w + "es"

        # consonant + 'y' -> 'ies'
        vowels = set("aeiou")
        if len(w) >= 2 and w[-1] in "yY" and w[-2].casefold() not in vowels:
            return w[:-1] + "ies"

        # Words ending with 'f' / 'fe' -> 'ves' (with some common exceptions)
        f_exceptions = {"roof", "chief", "chef", "belief", "cliff", "proof", "reef", "gulf", "brief"}
        if lw.endswith("fe") and lw[:-2] not in f_exceptions:
            return w[:-2] + "ves"
        if lw.endswith("f") and lw[:-1] not in f_exceptions:
            return w[:-1] + "ves"

        # Words ending with 'o' sometimes take 'es' (common subset)
        o_es = {"potato", "tomato", "hero", "echo", "torpedo", "veto"}
        if lw.endswith("o") and lw in o_es:
            return w + "es"

        # Default: just 's'
        return w + "s"

    key = word.casefold()

    if key in uncountables:
        plural_word = word  # unchanged
    elif key in irregulars:
        plural_word = _preserve_simple_case(word, irregulars[key])
    else:
        plural_word = _basic_rules(word)

    return f"{n} {plural_word}"
