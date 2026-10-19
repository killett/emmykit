"""`round_out`: round away from zero to N significant figures.

Expected values are worked out by hand from the decimal number as written.
"""

from __future__ import annotations

import pytest

from emmykit.humanize import round_out
from tests._helpers import run_python


@pytest.mark.parametrize(
    ("x", "digits"),
    [(1.11, 3), (2.3, 2), (0.123, 3), (-4.56, 3), (120.0, 2), (0.07, 1)],
)
def test_value_already_at_the_precision_is_unchanged(x: float, digits: int) -> None:
    """Fails if the binary error in e.g. 1.11 (1.1100000000000001) bumps it to 1.12."""
    assert round_out(x, digits) == x


@pytest.mark.parametrize(
    ("x", "digits", "expected"),
    [
        (1.111, 3, 1.12),
        (-1.111, 3, -1.12),
        (3.14159, 3, 3.15),
        (0.0001234, 2, 0.00013),
        (12345.0, 2, 13000.0),
        (-2.5, 0, -10.0),
    ],
)
def test_rounds_away_from_zero(x: float, digits: int, expected: float) -> None:
    """Positive values go up and negative values go down, to the nearest N-figure value."""
    assert round_out(x, digits) == expected


def test_result_has_no_binary_tail() -> None:
    """2.3 comes back as the float 2.3, not 2.3000000000000003."""
    assert repr(round_out(2.3, 2)) == "2.3"


@pytest.mark.parametrize("x", [0, 5, 1e-20])
def test_always_returns_a_plain_float(x: float) -> None:
    """Zero, ints and values below 10**-max_digits come back as floats too."""
    result = round_out(x)
    assert type(result) is float
    assert result == x


def test_works_without_numpy() -> None:
    """Plain arithmetic on one number shouldn't need the `datetime` extra."""
    result = run_python(
        "import sys\n"
        "sys.modules['numpy'] = None\n"
        "from emmykit import round_out\n"
        "print(round_out(1.111, 3))\n"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.12"
