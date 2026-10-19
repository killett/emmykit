"""`seconds_in_unit`: SI prefixes whose symbols differ only in case."""

from __future__ import annotations

import pytest

from emmykit.numeric_helpers import seconds_in_unit


@pytest.mark.parametrize(
    ("unit", "seconds"),
    [
        ("rs", 1e-27), ("rontosecond", 1e-27), ("rontoseconds", 1e-27),
        ("qs", 1e-30), ("quectosecond", 1e-30), ("quectoseconds", 1e-30),
        ("ronnaseconds", 1e27), ("quettasecond", 1e30),
        ("ms", 1e-3), ("megaseconds", 1e6),
    ],
)
def test_lowercase_symbol_is_the_small_prefix(unit: str, seconds: float) -> None:
    """Units are case-folded, so "rs" can only be one of rontosecond (r) and
    ronnasecond (R); like "ms", it means the small one. The big ones keep their names.
    """
    assert seconds_in_unit(unit) == seconds
