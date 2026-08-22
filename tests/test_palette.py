"""Palette value objects, the registry, and the WCAG contrast helper.

These tests are deliberately matplotlib-free: the palette is data, and the
data-level invariants must hold in an environment that never imports
matplotlib. The matplotlib bridge is exercised in `test_palette_mpl.py`.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from emmykit.palette import (
    MIN_CONTRAST_RATIO,
    Palette,
    _shift_to_contrast,
    contrast_ratio,
    palette,
    palette_names,
)

HEX_RE = re.compile(r"^#[0-9A-F]{6}$")


def _all_colors(pal: Palette) -> list[str]:
    """Return every colour a palette carries: series colours plus roles."""
    return [*pal.series, pal.background, pal.foreground, pal.grid]


# --------------------------------------------------------------------------
# contrast_ratio
# --------------------------------------------------------------------------


def test_white_on_black_is_the_wcag_maximum() -> None:
    """White against black is exactly 21:1, the ceiling the WCAG formula defines."""
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0)


def test_identical_colors_have_no_contrast() -> None:
    """A colour against itself is 1:1 — invisible."""
    assert contrast_ratio("#3E81A7", "#3E81A7") == pytest.approx(1.0)


def test_contrast_ratio_is_order_independent() -> None:
    """Swapping foreground and background must not change the ratio.

    Fails if the implementation subtracts instead of sorting the two
    luminances into (lighter + 0.05) / (darker + 0.05).
    """
    forward = contrast_ratio("#0072B2", "#FFFFFF")
    backward = contrast_ratio("#FFFFFF", "#0072B2")
    assert forward == pytest.approx(backward)


def test_mid_grey_on_white_matches_the_published_ratio() -> None:
    """`#767676` on white is the canonical 4.54:1 boundary grey.

    This pins the sRGB gamma linearization: a naive implementation that
    averages the raw 0-255 channels yields roughly 3.7:1 and would fail here.
    """
    assert contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)


def test_three_digit_hex_is_expanded() -> None:
    """`#FFF` means the same colour as `#FFFFFF`."""
    assert contrast_ratio("#FFF", "#000") == pytest.approx(21.0)


@pytest.mark.parametrize(
    "bad",
    ["FFFFFF", "#GGGGGG", "#FFFF", "", "white", "#FFFFFFFF"],
)
def test_unparseable_colors_are_rejected(bad: str) -> None:
    """A non-hex colour raises ValueError naming the offending string.

    Fails if the parser silently coerces (e.g. int(..., 16) on a truncated
    string) and returns a plausible-but-wrong ratio.
    """
    with pytest.raises(ValueError, match=re.escape(repr(bad))):
        contrast_ratio(bad, "#000000")


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def test_light_and_dark_are_registered() -> None:
    """The two named palettes the API promises are both present."""
    assert {"light", "dark"} <= set(palette_names())


def test_unknown_palette_name_lists_the_registered_names() -> None:
    """An unknown name raises ValueError naming both the bad key and the valid ones.

    Fails if lookup is a bare dict subscript, which raises KeyError with no
    hint about what the caller could have asked for instead.
    """
    with pytest.raises(ValueError) as excinfo:
        palette("solarized")
    message = str(excinfo.value)
    assert "solarized" in message
    for name in palette_names():
        assert name in message


def test_documented_import_forms_reach_the_same_function() -> None:
    """`from emmykit.palette import palette` and `emmykit.palette` agree.

    The top-level package rebinds the name `palette` from the submodule to the
    lookup function. Fails if the submodule scrub-list at the bottom of
    `emmykit/__init__.py` ever pops that name, which would delete the function
    from the flat public surface.
    """
    import emmykit

    assert emmykit.palette is palette
    assert emmykit.contrast_ratio is contrast_ratio


def test_lookup_returns_the_same_shared_instance() -> None:
    """Two lookups of one name return one object — palettes are values, not copies."""
    assert palette("dark") is palette("dark")


# --------------------------------------------------------------------------
# palette contents
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["light", "dark"])
def test_every_color_is_an_explicit_uppercase_hex_string(name: str) -> None:
    """No palette may carry a matplotlib colour *name*.

    This is the `lightpurple` regression test in its matplotlib-free form:
    `lightpurple` is in neither the CSS4 nor the base colour table, so any
    named colour is a `to_rgb` crash waiting for the caller who reaches it.
    """
    offenders = [c for c in _all_colors(palette(name)) if not HEX_RE.match(c)]
    assert not offenders, f"{name} palette holds non-hex colours: {offenders}"


@pytest.mark.parametrize("name", ["light", "dark"])
def test_series_colors_clear_the_documented_contrast_minimum(name: str) -> None:
    """Every series colour is readable on its *own* palette's background.

    This is the dark-mode defect: the old `colors` list kept `blue`
    (`#0000FF`, 2.4:1 on black) and `purple` (`#800080`, 2.2:1) in dark mode
    and relied on the caller remembering to reach for `lightcolors` instead.
    """
    pal = palette(name)
    too_faint = {
        color: round(contrast_ratio(color, pal.background), 2)
        for color in pal.series
        if contrast_ratio(color, pal.background) < MIN_CONTRAST_RATIO
    }
    assert not too_faint, (
        f"{name} series colours below {MIN_CONTRAST_RATIO}:1 on "
        f"{pal.background}: {too_faint}"
    )


@pytest.mark.parametrize("name", ["light", "dark"])
def test_series_is_a_usable_qualitative_length(name: str) -> None:
    """5-8 distinct colours: fewer is limiting, more stops being distinguishable.

    The distinctness half fails if the per-theme luminance adjustment drives
    two hues onto the same hex value, which would silently render two data
    series identically.
    """
    series = palette(name).series
    assert 5 <= len(series) <= 8
    assert len(set(series)) == len(series), f"duplicate colours in {series}"


def test_dark_palette_roles_match_the_documented_api() -> None:
    """The dark palette reads black-background / white-foreground.

    Fails if background and foreground are ever swapped, which would make
    every rc_params consumer draw white-on-white.
    """
    pal = palette("dark")
    assert pal.background == "#000000"
    assert pal.foreground == "#FFFFFF"


def test_light_palette_roles_match_the_documented_api() -> None:
    """The light palette reads white-background / black-foreground."""
    pal = palette("light")
    assert pal.background == "#FFFFFF"
    assert pal.foreground == "#000000"


@pytest.mark.parametrize("name", ["light", "dark"])
def test_foreground_is_readable_on_its_background(name: str) -> None:
    """Text and tick colour must clear the same minimum the series colours do."""
    pal = palette(name)
    assert contrast_ratio(pal.foreground, pal.background) >= MIN_CONTRAST_RATIO


# --------------------------------------------------------------------------
# palette construction
#
# `_shift_to_contrast` is private, but it is the guard that stops a future
# registered palette from shipping colours quietly below the threshold, and
# that guard is unreachable through the two palettes registered today.
# --------------------------------------------------------------------------


def test_shifting_returns_an_already_readable_color_untouched() -> None:
    """A colour that already clears the threshold is not adjusted at all.

    This is what keeps the Okabe-Ito values verbatim wherever they already
    work: `#E69F00` is 9.32:1 on black. Fails if the shift always blends by
    some fixed amount, which would drift the published set for no reason.
    """
    assert _shift_to_contrast("#E69F00", "#000000", "#FFFFFF", 4.5) == "#E69F00"


def test_shifting_stops_as_soon_as_the_threshold_is_met() -> None:
    """The result clears the minimum but the step before it does not.

    Fails if the search overshoots — washing every adjusted colour out
    toward white or black further than readability requires.
    """
    shifted = _shift_to_contrast("#0072B2", "#000000", "#FFFFFF", 4.5)
    assert shifted != "#0072B2"
    assert contrast_ratio(shifted, "#000000") >= 4.5
    assert contrast_ratio("#0072B2", "#000000") < 4.5


def test_an_unreachable_threshold_raises_rather_than_returning_a_faint_color() -> None:
    """No blend can clear 4.5:1 against mid-grey, so construction must fail loudly.

    A mid-grey background caps contrast at about 3.9:1 toward white and 5.3:1
    toward black. Fails if the search runs out of steps and silently returns
    the last (still unreadable) candidate — which would put a palette in the
    registry that violates the guarantee the registry exists to make.
    """
    with pytest.raises(ValueError, match="cannot reach"):
        _shift_to_contrast("#808080", "#808080", "#FFFFFF", MIN_CONTRAST_RATIO)


# --------------------------------------------------------------------------
# immutability
# --------------------------------------------------------------------------


def test_palette_attributes_cannot_be_reassigned() -> None:
    """Palettes are frozen: assigning to a field raises.

    Because lookups are shared instances, a mutable palette would let one
    caller retheme every subsequent caller in the process.
    """
    pal = palette("light")
    with pytest.raises(dataclasses.FrozenInstanceError):
        pal.background = "#123456"  # type: ignore[misc]


def test_series_is_an_immutable_sequence() -> None:
    """`series` is a tuple, so `.append` is not even reachable."""
    assert isinstance(palette("dark").series, tuple)


def test_mutating_a_returned_color_list_cannot_corrupt_the_registry() -> None:
    """Colour lists handed out are per-call copies.

    Fails if the palette hands out a reference to one shared list, so that a
    caller doing `colors.append(...)` or `colors.clear()` poisons the palette
    for the next caller in the same process.
    """
    before = list(palette("dark").series)
    stolen = list(palette("dark").series)
    stolen.append("#BADBAD")
    stolen[0] = "#BADBAD"
    assert list(palette("dark").series) == before
