"""Characterization tests pinning `human_bytesize` byte-for-byte.

`human_bytesize` is published and has downstream callers, so its output is
frozen: every assertion here describes behaviour that existed *before*
`humanize` grew a general quantity formatter, including the quirks
(`inf` clamping to the largest prefix, no prefix promotion after rounding)
that the general formatter deliberately does *not* inherit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from emmykit.humanize import human_bytesize

BASELINE = json.loads(
    (Path(__file__).parent / "_baseline_human_bytesize.json").read_text()
)

_VALUES: dict[str, float | None] = {
    "None": None,
    "nan": float("nan"),
    "inf": float("inf"),
    "-inf": float("-inf"),
}


def _decode_value(raw: str) -> float | int | None:
    """Rebuild a baseline case's input value from its recorded repr."""
    if raw in _VALUES:
        return _VALUES[raw]
    return eval(raw)  # noqa: S307 - reprs of numeric literals we wrote ourselves


def _decode_kwargs(key: str) -> dict[str, object]:
    """Rebuild a baseline case's keyword arguments from its recorded key."""
    suffix, si, precision, space, trim, long_units = key.split(",")
    return {
        "suffix": suffix,
        "si": bool(int(si)),
        "precision": int(precision),
        "space": bool(int(space)),
        "trim_trailing_zeros": bool(int(trim)),
        "long_units": bool(int(long_units)),
    }


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda c: f"{c[0]}|{c[1]}")
def test_human_bytesize_matches_frozen_baseline(case: list[str]) -> None:
    """Every recorded (value, options) pair must reproduce its frozen output.

    Fails if any refactor changes a formatted string or an exception message
    for any point in the full option matrix.
    """
    raw_value, key, kind, expected = case
    value = _decode_value(raw_value)
    kwargs = _decode_kwargs(key)
    if kind == "ok":
        assert human_bytesize(value, **kwargs) == expected  # type: ignore[arg-type]
    else:
        with pytest.raises(Exception) as exc_info:
            human_bytesize(value, **kwargs)  # type: ignore[arg-type]
        assert f"{type(exc_info.value).__name__}: {exc_info.value}" == expected


def test_iec_is_the_default_system() -> None:
    """1536 bytes is 1.5 KiB: the default step is 1024, not 1000."""
    assert human_bytesize(1536) == "1.5 KiB"


def test_si_uses_powers_of_1000() -> None:
    """With si=True, 1500 bytes is 1.5 kB."""
    assert human_bytesize(1500, si=True) == "1.5 kB"


def test_long_units_si_spells_out_megabytes() -> None:
    """Long SI output composes the prefix name with "bytes"."""
    assert human_bytesize(1_500_000, si=True, long_units=True) == "1.5 megabytes"


def test_long_units_iec_spells_out_kibibytes() -> None:
    """Long IEC output uses the binary prefix name, not the SI one."""
    assert human_bytesize(1536, long_units=True) == "1.5 kibibytes"


def test_long_units_non_byte_suffix_appends_the_suffix() -> None:
    """A non-"B" suffix is appended raw to the long prefix name."""
    assert human_bytesize(1500, suffix="W", si=True, long_units=True) == "1.5 kiloW"


def test_none_returns_the_string_none() -> None:
    """None is formatted as the literal string "None", not raised on."""
    assert human_bytesize(None) == "None"


def test_negative_keeps_leading_minus() -> None:
    """Negative sizes keep a leading minus and are scaled by magnitude."""
    assert human_bytesize(-1536) == "-1.5 KiB"


def test_space_false_joins_number_and_unit() -> None:
    """space=False removes the separator between number and unit."""
    assert human_bytesize(1536, space=False) == "1.5KiB"


def test_trim_trailing_zeros_drops_the_decimal_point() -> None:
    """trim_trailing_zeros strips zeros and any dangling point."""
    assert human_bytesize(1024, trim_trailing_zeros=True) == "1 KiB"


def test_width_constrained_mode_fills_the_width_with_decimals() -> None:
    """precision=-8 yields exactly 8 characters, maximizing decimal places."""
    result = human_bytesize(1536, precision=-8)
    assert result == "1.50 KiB"
    assert len(result) == 8


def test_width_constrained_mode_right_justifies_a_short_numeric_part() -> None:
    """A numeric part narrower than its field is right-justified, not padded right."""
    assert human_bytesize(1536, precision=-8, trim_trailing_zeros=True) == " 1.5 KiB"


def test_width_constrained_mode_forces_long_units_off() -> None:
    """long_units is ignored in width-constrained mode."""
    assert human_bytesize(1536, precision=-8, long_units=True) == "1.50 KiB"


def test_width_too_small_for_unit_raises_with_exact_message() -> None:
    """No room for any digits raises ValueError naming unit and space."""
    with pytest.raises(ValueError) as exc_info:
        human_bytesize(1536, precision=-4)
    assert str(exc_info.value) == (
        "precision=-4 is too small: no room for numeric part "
        "(unit='KiB', space=True)"
    )


def test_width_too_small_for_value_raises_with_exact_message() -> None:
    """A value whose integer form will not fit reports the minimum width."""
    with pytest.raises(ValueError) as exc_info:
        human_bytesize(1023 * 1024, precision=-6)
    assert str(exc_info.value) == (
        "precision=-6 is too small for this value; "
        "need at least -8 or less (space=True, si=False)"
    )


def test_infinity_clamps_to_the_largest_prefix() -> None:
    """Legacy quirk: inf walks the whole prefix table instead of short-circuiting."""
    assert human_bytesize(float("inf")) == "inf QiB"
    assert human_bytesize(float("-inf"), si=True) == "-inf QB"


def test_nan_formats_without_a_prefix() -> None:
    """nan compares false against the step, so it keeps the empty prefix."""
    assert human_bytesize(float("nan")) == "nan B"


def test_rounding_does_not_promote_to_the_next_prefix() -> None:
    """Legacy quirk: 999999 B rounds to "1000.0 kB", it is not promoted to MB."""
    assert human_bytesize(999_999, si=True) == "1000.0 kB"


def test_values_below_one_keep_the_empty_prefix() -> None:
    """Legacy quirk: sub-unit values never reach a submultiple prefix."""
    assert human_bytesize(0.5) == "0.5 B"
    assert human_bytesize(0.0001, si=True, precision=4) == "0.0001 B"
