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
    WATTS,
    _resolve_as_unit,
    choose_prefix,
    human_quantity,
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
    """"centimeter" is matched via the unit's singular name.

    Asserts the same (factor, symbol, long_prefix) triple as its plural
    sibling, not just the long_input flag — a resolver that matched the
    singular tail but returned the wrong factor would otherwise pass.
    """
    resolved = _resolve_as_unit("centimeter", METERS, "si")
    assert (resolved.factor, resolved.symbol, resolved.long_prefix) == (
        pytest.approx(0.01), "c", "centi")
    assert resolved.long_input is True


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


def test_forced_unit_overrides_engineering_mode() -> None:
    """centi is absent from engineering mode, but asking for it by name works.

    Fails if `as_unit` is validated against the mode's table instead of the
    full prefix set.
    """
    assert human_quantity(0.02, METERS, as_unit="cm") == "2.0 cm"


def test_forced_unit_long_input_gives_long_output() -> None:
    """The spelling of the request decides the spelling of the result."""
    assert human_quantity(0.02, METERS, as_unit="centimeters") == "2.0 centimeters"


def test_forced_binary_unit_needs_no_system_argument() -> None:
    """"KiB" implies the binary system, so 1536 B is 1.5 KiB with no system=.

    Also covers system="iec" explicitly agreeing with the binary prefix —
    only the conflicting case (binary prefix + system="si") was covered
    before, so a future guard that over-rejects any explicit `system`
    argument would still have passed.
    """
    assert human_quantity(1536, BYTES, as_unit="KiB") == "1.5 KiB"
    assert human_quantity(1536, BYTES, as_unit="kibibytes") == "1.5 kibibytes"
    assert human_quantity(1536, BYTES, as_unit="KiB", system="iec") == "1.5 KiB"


def test_explicit_long_units_false_beats_a_long_request() -> None:
    """long_units=False is a deliberate choice and must win over the spelling."""
    assert human_quantity(0.02, METERS, as_unit="centimeters",
                          long_units=False) == "2.0 cm"


def test_explicit_long_units_true_beats_a_short_request() -> None:
    """long_units=True composes the long prefix even from a symbol request."""
    assert human_quantity(0.02, METERS, as_unit="cm",
                          long_units=True) == "2.0 centimeters"


def test_forced_unit_keeps_the_existing_plural_rule() -> None:
    """The number decides singular vs plural, not the requested spelling."""
    assert human_quantity(0.01, METERS, as_unit="centimeter",
                          precision=0) == "1 centimeter"
    assert human_quantity(0.02, METERS, as_unit="centimeter") == "2.0 centimeters"


def test_forced_unit_is_not_promoted_after_rounding() -> None:
    """999.99 kW rounds to 1000.0 but the caller asked for kW, so it stays kW.

    Fails if the promotion step still runs on a forced prefix, silently
    relabelling the axis the caller pinned.
    """
    assert human_quantity(999_999, WATTS, as_unit="kW") == "1000.0 kW"


def test_forced_unit_applies_to_zero_and_non_finite_values() -> None:
    """A pinned scale must label every tick, including 0, nan and inf."""
    assert human_quantity(0, METERS, as_unit="cm") == "0.0 cm"
    assert human_quantity(float("nan"), METERS, as_unit="cm") == "nan cm"
    assert human_quantity(float("inf"), METERS, as_unit="cm") == "inf cm"
    assert human_quantity(float("-inf"), METERS, as_unit="cm") == "-inf cm"


def test_forced_unit_respects_space_and_trim() -> None:
    """The existing formatting switches keep working under a forced prefix."""
    assert human_quantity(0.02, METERS, as_unit="cm", space=False) == "2.0cm"
    assert human_quantity(0.01, METERS, as_unit="cm",
                          trim_trailing_zeros=True) == "1 cm"


def test_forced_unit_in_width_mode_uses_the_symbol_form() -> None:
    """Width mode is symbol-only, so a long request still measures as "cm"."""
    result = human_quantity(0.02, METERS, as_unit="centimeters", precision=-7)
    assert result == "2.00 cm"
    assert len(result) == 7


def test_forced_micro_keeps_the_requested_spelling() -> None:
    """"um" stays ASCII and "µm" stays U+00B5, whatever ascii_micro says."""
    assert human_quantity(2e-6, METERS, as_unit="um") == "2.0 um"
    assert human_quantity(2e-6, METERS, as_unit="µm", ascii_micro=True) == "2.0 µm"


def test_forced_unit_can_ask_for_no_prefix_at_all() -> None:
    """"m" pins the bare unit, defeating automatic promotion to km."""
    assert human_quantity(1500, METERS, as_unit="m") == "1500.0 m"


def test_decimal_request_under_explicit_binary_system_raises() -> None:
    """The one real conflict still raises at the public boundary."""
    with pytest.raises(ValueError, match="does not exist in the binary system"):
        human_quantity(0.02, METERS, system="iec", as_unit="cm")


def test_as_unit_none_is_unchanged_automatic_behaviour() -> None:
    """The default path must be untouched: 0.02 m is still 20.0 mm."""
    assert human_quantity(0.02, METERS) == "20.0 mm"
    assert human_quantity(0.02, METERS, as_unit=None) == "20.0 mm"


def test_choose_prefix_returns_the_requested_scale() -> None:
    """An axis pinned to cm gets centi and 0.01 whatever its ticks say.

    Fails if the forced path still consults the values and picks milli.
    """
    symbol, factor = choose_prefix([0.001, 0.002], METERS, as_unit="cm")
    assert symbol == "c"
    assert factor == pytest.approx(0.01)
    assert [f"{v / factor:.1f}" for v in [0.001, 0.002]] == ["0.1", "0.2"]


def test_choose_prefix_long_request_returns_the_long_prefix() -> None:
    """"centimeters" gives ("centi", 0.01) so the label composes in words."""
    assert choose_prefix([0.02], METERS, as_unit="centimeters") == ("centi", 0.01)


def test_choose_prefix_does_not_consume_values_when_pinned() -> None:
    """The values are irrelevant to a pinned scale, so they must not be read.

    Fails if the implementation scans first and forces afterwards — this
    generator raises the moment anything iterates it.
    """
    def exploding():
        raise AssertionError("values must not be consumed when as_unit is given")
        yield 1.0  # pragma: no cover

    assert choose_prefix(exploding(), METERS, as_unit="cm") == ("c", 0.01)


@pytest.mark.parametrize(
    "values", [[], [0.0, 0, -0.0], [float("nan"), float("inf")]],
    ids=["empty", "all-zero", "all-non-finite"],
)
def test_choose_prefix_pinned_scale_survives_degenerate_input(
    values: list[float],
) -> None:
    """The cases that fall back to ("", 1.0) automatically stay pinned."""
    assert choose_prefix(values, METERS, as_unit="cm") == ("c", 0.01)


def test_choose_prefix_binary_request() -> None:
    """"KiB" pins a byte axis to 1024 without a system argument."""
    assert choose_prefix([2048.0], BYTES, as_unit="KiB") == ("Ki", 1024.0)


def test_choose_prefix_requires_a_unit_to_parse_against() -> None:
    """as_unit is parsed against the unit, so omitting the unit is an error."""
    with pytest.raises(ValueError, match="as_unit needs the unit"):
        choose_prefix([1.0], as_unit="cm")


def test_choose_prefix_without_as_unit_is_unchanged() -> None:
    """The automatic path must be untouched."""
    assert choose_prefix([0.001, 0.002, 0.011], METERS) == ("m", 0.001)
