"""Tests for `as_unit`: the caller naming the output unit outright.

Expected factors and prefixes come from the SI/IEC tables by hand, never by
running the implementation.
"""

from __future__ import annotations

import pytest

from emmykit.humanize import (
    BYTES,
    HERTZ,
    METERS,
    _resolve_as_unit,
)


def test_symbol_prefix_resolves_to_factor_and_both_spellings() -> None:
    """"cm" is centi (1e-2) on metres, and carries its long spelling along.

    Fails if the resolver returns only the spelling it was given, which would
    leave `long_units=True` with no long prefix to compose.
    """
    resolved = _resolve_as_unit("cm", METERS, "si")
    assert resolved.factor == pytest.approx(0.01)
    assert resolved.symbol == "c"
    assert resolved.long_prefix == "centi"
    assert resolved.long_input is False
    assert resolved.system == "si"


def test_long_input_sets_the_long_input_flag() -> None:
    """"centimeters" resolves identically but marks the input as long-form."""
    resolved = _resolve_as_unit("centimeters", METERS, "si")
    assert (resolved.factor, resolved.symbol, resolved.long_prefix) == (
        pytest.approx(0.01), "c", "centi")
    assert resolved.long_input is True


def test_singular_long_input_is_accepted() -> None:
    """"centimeter" is matched via the unit's singular name."""
    assert _resolve_as_unit("centimeter", METERS, "si").long_input is True


def test_binary_prefix_implies_the_binary_system() -> None:
    """"KiB" is 1024 and switches the system, so no system= is needed.

    Fails if the resolver reports "si" and the caller silently divides by 1000.
    """
    resolved = _resolve_as_unit("KiB", BYTES, "si")
    assert resolved.factor == 1024.0
    assert resolved.system == "iec"
    assert (resolved.symbol, resolved.long_prefix) == ("Ki", "kibi")


def test_binary_long_input() -> None:
    """"kibibytes" resolves through the unit's plural name."""
    resolved = _resolve_as_unit("kibibytes", BYTES, "si")
    assert (resolved.factor, resolved.long_prefix, resolved.long_input) == (
        1024.0, "kibi", True)


@pytest.mark.parametrize(
    "text,unit,long_input",
    [("m", METERS, False), ("meters", METERS, True), ("meter", METERS, True),
     ("B", BYTES, False), ("bytes", BYTES, True), ("Hz", HERTZ, False),
     ("hertz", HERTZ, True)],
)
def test_bare_unit_resolves_to_the_identity_scale(
    text: str, unit: object, long_input: bool
) -> None:
    """A unit with no prefix is factor 1.0 and empty prefixes, not an error."""
    resolved = _resolve_as_unit(text, unit, "si")  # type: ignore[arg-type]
    assert (resolved.factor, resolved.symbol, resolved.long_prefix) == (1.0, "", "")
    assert resolved.long_input is long_input


def test_both_micro_spellings_are_accepted_and_echoed() -> None:
    """"µm" and "um" are the same scale; each keeps the spelling it was given.

    Fails if the resolver normalises to one sign, which would make ascii_micro
    unreachable for a caller who spelled it out.
    """
    assert _resolve_as_unit("µm", METERS, "si").symbol == "µ"
    assert _resolve_as_unit("um", METERS, "si").symbol == "u"
    assert _resolve_as_unit("um", METERS, "si").factor == pytest.approx(1e-6)
    assert _resolve_as_unit("um", METERS, "si").long_prefix == "micro"


def test_deka_is_reachable_by_name() -> None:
    """"dam" is deka (1e1), a prefix automatic engineering mode never picks."""
    resolved = _resolve_as_unit("dam", METERS, "si")
    assert (resolved.factor, resolved.symbol) == (10.0, "da")


def test_non_string_raises_type_error() -> None:
    """A Unit passed where a string belongs fails loudly, not by string-format."""
    with pytest.raises(TypeError, match="as_unit must be a string"):
        _resolve_as_unit(METERS, METERS, "si")  # type: ignore[arg-type]


def test_wrong_unit_tail_names_the_unit_passed() -> None:
    """"cg" against METERS is a mismatch; the message must show what was expected."""
    with pytest.raises(ValueError) as exc_info:
        _resolve_as_unit("cg", METERS, "si")
    message = str(exc_info.value)
    assert "'cg'" in message
    assert "'m'" in message and "'meter'" in message and "'meters'" in message


def test_empty_string_is_a_tail_mismatch() -> None:
    """"" carries no unit, so it fails like any other non-matching tail."""
    with pytest.raises(ValueError, match="does not end in the unit"):
        _resolve_as_unit("", METERS, "si")


def test_unknown_prefix_explains_the_case_rule() -> None:
    """"KB" must not be guessed into kB or KiB; the message names both."""
    with pytest.raises(ValueError) as exc_info:
        _resolve_as_unit("KB", BYTES, "si")
    message = str(exc_info.value)
    assert "unknown prefix 'K'" in message
    assert "'k'" in message and "'Ki'" in message


def test_mixed_spellings_are_rejected() -> None:
    """A long prefix on a symbol unit ("centim") is a spelling mix, not a prefix."""
    with pytest.raises(ValueError, match="mixes spellings"):
        _resolve_as_unit("centim", METERS, "si")


def test_mixed_spellings_the_other_way_are_rejected() -> None:
    """A symbol prefix on a long unit ("cmeters") is the mirror mistake."""
    with pytest.raises(ValueError, match="mixes spellings"):
        _resolve_as_unit("cmeters", METERS, "si")


def test_decimal_prefix_under_an_explicit_binary_system_raises() -> None:
    """system="iec" is never a default, so "cm" against it is a real conflict."""
    with pytest.raises(ValueError) as exc_info:
        _resolve_as_unit("cm", METERS, "iec")
    message = str(exc_info.value)
    assert "'cm'" in message and "iec" in message
