"""Tests for the general quantity formatter: `Unit`, `human_quantity`, `choose_prefix`.

Expected strings are derived from the SI/IEC prefix tables by hand, never by
running the implementation.
"""

from __future__ import annotations

import dataclasses

import pytest

from emmykit.humanize import (
    BYTES,
    GRAMS,
    HERTZ,
    JOULES,
    METERS,
    SECONDS,
    WATTS,
    Unit,
    choose_prefix,
    human_quantity,
)

# --------------------------------------------------------------------------
# Unit value object
# --------------------------------------------------------------------------


def test_unit_carries_symbol_and_both_long_names() -> None:
    """A Unit stores the three strings needed to render short and long output.

    Fails if the long names are derived from the symbol instead of stored.
    """
    assert (METERS.symbol, METERS.singular, METERS.plural) == ("m", "meter", "meters")
    assert (BYTES.symbol, BYTES.singular, BYTES.plural) == ("B", "byte", "bytes")


def test_hertz_has_no_plural_s() -> None:
    """"hertz" is its own plural; a naive symbol+"s" rule would produce "hertzs"."""
    assert HERTZ.plural == "hertz"


def test_ready_made_units_cover_the_documented_set() -> None:
    """The advertised units exist with the correct symbols."""
    symbols = [u.symbol for u in (BYTES, METERS, GRAMS, SECONDS, JOULES, WATTS)]
    assert symbols == ["B", "m", "g", "s", "J", "W"]


def test_unit_is_immutable() -> None:
    """Units are shared module-level constants, so mutating one must raise."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        METERS.symbol = "km"  # type: ignore[misc]


# --------------------------------------------------------------------------
# human_quantity - short form
# --------------------------------------------------------------------------


def test_zettajoules_short_form() -> None:
    """3.2e21 J is 3.2 ZJ: Z is 10^21.

    Fails if the multiples table skips or misorders a prefix.
    """
    assert human_quantity(3.2e21, JOULES) == "3.2 ZJ"


def test_submultiple_engineering_uses_milli() -> None:
    """0.02 m in engineering mode is 20.0 mm: only powers of 1000 are allowed."""
    assert human_quantity(0.02, METERS) == "20.0 mm"


def test_submultiple_full_si_uses_centi() -> None:
    """0.02 m in full SI is 2.0 cm: centi (1e-2) is available."""
    assert human_quantity(0.02, METERS, mode="full_si") == "2.0 cm"


def test_full_si_allows_deka_for_multiples() -> None:
    """20 m in full SI is 2.0 dam: deka (1e1) is a multiple, not a submultiple."""
    assert human_quantity(20, METERS, mode="full_si") == "2.0 dam"


def test_engineering_mode_never_uses_deka() -> None:
    """20 m in engineering mode stays 20.0 m; da is outside powers of 1000."""
    assert human_quantity(20, METERS) == "20.0 m"


def test_micro_uses_the_u00b5_sign() -> None:
    """2e-6 m is 2.0 µm with U+00B5, the documented micro sign."""
    assert human_quantity(2e-6, METERS) == "2.0 µm"


def test_ascii_micro_option_emits_plain_u() -> None:
    """ascii_micro=True swaps µ for "u" for ASCII-only sinks."""
    assert human_quantity(2e-6, METERS, ascii_micro=True) == "2.0 um"


def test_iec_system_uses_binary_steps() -> None:
    """1536 B with system="iec" is 1.5 KiB (1536/1024)."""
    assert human_quantity(1536, BYTES, system="iec") == "1.5 KiB"


def test_si_system_is_the_default_for_bytes() -> None:
    """Unlike human_bytesize, the general formatter defaults to decimal prefixes."""
    assert human_quantity(1500, BYTES) == "1.5 kB"


def test_negative_values_keep_the_sign_and_scale_by_magnitude() -> None:
    """-1500 m is -1.5 km: the prefix comes from the magnitude, the sign is kept."""
    assert human_quantity(-1500, METERS) == "-1.5 km"


def test_space_and_trim_options_are_honoured() -> None:
    """space=False joins number and unit; trim drops the trailing ".0"."""
    assert human_quantity(1500, METERS, space=False) == "1.5km"
    assert human_quantity(1000, METERS, trim_trailing_zeros=True) == "1 km"


def test_precision_controls_decimal_places() -> None:
    """precision=3 keeps three decimals."""
    assert human_quantity(1234, WATTS, precision=3) == "1.234 kW"


def test_none_formats_as_the_string_none() -> None:
    """None is formatted, not raised on, matching human_bytesize."""
    assert human_quantity(None, METERS) == "None"


# --------------------------------------------------------------------------
# human_quantity - long form
# --------------------------------------------------------------------------


def test_long_form_composes_prefix_and_plural_unit() -> None:
    """kilo + meters is "kilometers", not "kilo meters" or "kilometerss"."""
    assert human_quantity(1500, METERS, long_units=True) == "1.5 kilometers"


def test_long_form_zettajoules() -> None:
    """zetta + joules is "zettajoules"."""
    assert human_quantity(3.2e21, JOULES, long_units=True) == "3.2 zettajoules"


def test_long_form_binary_prefix_is_kibi() -> None:
    """IEC long names use the binary prefix: "kibibytes", not "kilobytes"."""
    assert human_quantity(1536, BYTES, system="iec", long_units=True) == "1.5 kibibytes"


def test_long_form_respects_a_unit_without_a_plural_s() -> None:
    """kilo + hertz stays "kilohertz"; a hardcoded "+s" would say "kilohertzs"."""
    assert human_quantity(2000, HERTZ, long_units=True) == "2.0 kilohertz"


def test_long_form_uses_the_singular_at_exactly_one() -> None:
    """A formatted value of exactly "1" reads "1 meter", not "1 meters"."""
    assert human_quantity(1, METERS, precision=0, long_units=True) == "1 meter"
    assert human_quantity(1000, METERS, trim_trailing_zeros=True,
                          long_units=True) == "1 kilometer"


def test_long_form_stays_plural_when_decimals_are_shown() -> None:
    """"1.0" is not the bare "1", so the plural is kept."""
    assert human_quantity(1, METERS, long_units=True) == "1.0 meters"


def test_long_form_submultiple_names() -> None:
    """milli + seconds is "milliseconds"; micro long name is "micro", not "µ"."""
    assert human_quantity(0.002, SECONDS, long_units=True) == "2.0 milliseconds"
    assert human_quantity(2e-6, SECONDS, long_units=True) == "2.0 microseconds"


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------


def test_rounding_across_a_boundary_promotes_the_prefix() -> None:
    """999999 W rounds to 1000.0 k at precision=1, so it must promote to 1.0 MW.

    Fails if the prefix is chosen before rounding and never re-checked.
    """
    assert human_quantity(999_999, WATTS) == "1.0 MW"


def test_rounding_below_the_boundary_does_not_promote() -> None:
    """999400 W rounds to 999.4 k, which stays in kilo."""
    assert human_quantity(999_400, WATTS) == "999.4 kW"


def test_zero_gets_no_prefix() -> None:
    """0 must not fall into the submultiple loop and spin down to quecto."""
    assert human_quantity(0, METERS) == "0.0 m"
    assert human_quantity(0.0, METERS, mode="full_si", long_units=True) == "0.0 meters"


def test_negative_zero_has_no_minus_sign() -> None:
    """-0.0 formats like 0.0; a `num < 0` sign test would be wrong here anyway."""
    assert human_quantity(-0.0, METERS) == "0.0 m"


def test_nan_and_infinity_get_no_prefix() -> None:
    """Non-finite values bypass prefix selection entirely.

    Fails if inf walks the table and comes out as "inf Qm".
    """
    assert human_quantity(float("nan"), METERS) == "nan m"
    assert human_quantity(float("inf"), METERS) == "inf m"
    assert human_quantity(float("-inf"), METERS) == "-inf m"
    assert human_quantity(float("inf"), METERS, long_units=True) == "inf meters"


def test_exact_power_of_the_step_lands_on_the_larger_prefix() -> None:
    """1000 W is 1.0 kW, not 1000.0 W: the boundary is inclusive upward."""
    assert human_quantity(1000, WATTS) == "1.0 kW"


def test_exact_binary_power_lands_on_the_larger_prefix() -> None:
    """1024 B in IEC is 1.0 KiB, not 1024.0 B."""
    assert human_quantity(1024, BYTES, system="iec") == "1.0 KiB"


def test_exact_submultiple_power_lands_on_the_larger_prefix() -> None:
    """0.001 m is 1.0 mm, not 1000.0 µm: the boundary belongs to milli."""
    assert human_quantity(0.001, METERS) == "1.0 mm"


def test_values_above_the_largest_prefix_clamp_to_quetta() -> None:
    """1e35 W has no prefix of its own; it clamps to Q rather than overflowing."""
    assert human_quantity(1e35, WATTS) == "100000.0 QW"


def test_values_below_the_smallest_prefix_clamp_to_quecto() -> None:
    """1e-35 m clamps to q instead of walking off the end of the table."""
    assert human_quantity(1e-35, METERS) == "0.0 qm"


def test_iec_below_one_clamps_to_no_prefix() -> None:
    """Binary systems have no submultiples, so 0.5 B stays 0.5 B."""
    assert human_quantity(0.5, BYTES, system="iec") == "0.5 B"


def test_iec_rejects_an_explicit_submultiple_mode() -> None:
    """Asking for SI submultiples in a binary system is an error, not a fallback."""
    with pytest.raises(ValueError, match="submultiple"):
        human_quantity(0.5, BYTES, system="iec", mode="full_si")
    with pytest.raises(ValueError, match="submultiple"):
        choose_prefix([0.5], BYTES, system="iec", mode="full_si")


def test_passing_a_bare_symbol_string_instead_of_a_unit_is_rejected() -> None:
    """`human_quantity(1.0, "m")` would otherwise format as "1.0 <str>"-ish nonsense."""
    with pytest.raises(TypeError, match="must be a Unit"):
        human_quantity(1.0, "m")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a Unit"):
        choose_prefix([1.0], "m")  # type: ignore[arg-type]


def test_choose_prefix_unit_is_optional() -> None:
    """The unit is documentation for the call site, so omitting it still works."""
    assert choose_prefix([1500.0]) == ("k", 1000.0)


def test_unknown_system_and_mode_are_rejected() -> None:
    """Typos in `system`/`mode` fail loudly instead of silently picking a default."""
    with pytest.raises(ValueError, match="system"):
        human_quantity(1.0, METERS, system="metric")
    with pytest.raises(ValueError, match="mode"):
        human_quantity(1.0, METERS, mode="scientific")


def test_width_constrained_mode_accounts_for_a_two_character_prefix() -> None:
    """"cm" is two characters wide, so the numeric field must shrink to fit 7 total."""
    result = human_quantity(0.02, METERS, mode="full_si", precision=-7)
    assert result == "2.00 cm"
    assert len(result) == 7


def test_width_constrained_mode_accounts_for_the_micro_sign() -> None:
    """The micro sign is one character but two UTF-8 bytes; width counts characters."""
    result = human_quantity(2e-6, METERS, precision=-7)
    assert result == "2.00 µm"
    assert len(result) == 7


def test_width_constrained_mode_raises_when_the_unit_fills_the_width() -> None:
    """No room for digits is a ValueError, not a silently over-long string."""
    with pytest.raises(ValueError, match="no room for numeric part"):
        human_quantity(0.02, METERS, mode="full_si", precision=-3)


# --------------------------------------------------------------------------
# choose_prefix - one scale for a whole set
# --------------------------------------------------------------------------


def test_choose_prefix_picks_one_scale_from_the_largest_value() -> None:
    """Ticks up to 0.011 m share centi in full SI: 0.011/0.01 = 1.1.

    Fails if each value is scaled independently (the "1 mm, 2 mm, 1 cm" bug).
    """
    symbol, factor = choose_prefix([0.001, 0.002, 0.011], METERS, mode="full_si")
    assert symbol == "c"
    assert factor == pytest.approx(0.01)
    assert [f"{v / factor:.1f}" for v in [0.001, 0.002, 0.011]] == ["0.1", "0.2", "1.1"]


def test_choose_prefix_engineering_mode_picks_milli_for_the_same_set() -> None:
    """The same set in engineering mode shares milli, since centi is unavailable."""
    symbol, factor = choose_prefix([0.001, 0.002, 0.011], METERS)
    assert symbol == "m"
    assert factor == pytest.approx(0.001)


def test_choose_prefix_ignores_nan_and_infinity() -> None:
    """Non-finite ticks must not drag the scale to the top of the table."""
    assert choose_prefix([1500.0, float("nan"), float("inf")], METERS) == ("k", 1000.0)


def test_choose_prefix_uses_magnitude_not_signed_value() -> None:
    """-2500 has the largest magnitude, so kilo is chosen despite the sign."""
    symbol, factor = choose_prefix([-2500.0, 1.0], METERS)
    assert (symbol, factor) == ("k", 1000.0)


def test_choose_prefix_all_zero_returns_the_identity_scale() -> None:
    """An all-zero axis gets no prefix and a divisor of 1.0, not a division by zero."""
    assert choose_prefix([0.0, 0, -0.0], METERS) == ("", 1.0)


def test_choose_prefix_empty_returns_the_identity_scale() -> None:
    """An empty tick list is handled explicitly rather than raising or clamping."""
    assert choose_prefix([], METERS) == ("", 1.0)


def test_choose_prefix_all_non_finite_returns_the_identity_scale() -> None:
    """A set with nothing finite in it behaves like the empty set."""
    assert choose_prefix([float("nan"), float("inf")], METERS) == ("", 1.0)


def test_choose_prefix_accepts_any_iterable_including_a_generator() -> None:
    """The values argument is consumed once, so a generator must work."""
    assert choose_prefix((v for v in [2e6, 3e6]), WATTS) == ("M", 1e6)


def test_choose_prefix_iec_returns_binary_factors() -> None:
    """IEC scaling divides by 1024, not 1000."""
    assert choose_prefix([1536.0], BYTES, system="iec") == ("Ki", 1024.0)


def test_choose_prefix_ascii_micro_option() -> None:
    """ascii_micro applies to the shared-scale symbol too."""
    assert choose_prefix([2e-6], METERS)[0] == "µ"
    assert choose_prefix([2e-6], METERS, ascii_micro=True)[0] == "u"


def test_choose_prefix_agrees_with_single_value_formatting() -> None:
    """A one-element set gets the same scale the single-value formatter uses."""
    symbol, factor = choose_prefix([3.2e21], JOULES)
    assert (symbol, factor) == ("Z", 1e21)
    assert human_quantity(3.2e21, JOULES) == f"{3.2e21 / factor:.1f} {symbol}J"
