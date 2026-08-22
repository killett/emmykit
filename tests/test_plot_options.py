"""`PlotOptions` after the palette extraction: a thin, still-compatible shim.

The colour attributes must keep working for existing callers, but they are now
views onto a `Palette` rather than hand-maintained lists.
"""

from __future__ import annotations

import re

import pytest

from emmykit.options import PlotOptions
from emmykit.palette import MIN_CONTRAST_RATIO, contrast_ratio, palette

HEX_RE = re.compile(r"^#[0-9A-F]{6}$")


def test_default_is_the_light_palette() -> None:
    """A fresh PlotOptions carries the light palette and mirrors its colours."""
    options = PlotOptions()
    assert options.palette is palette("light")
    assert options.colors == list(palette("light").series)
    assert options.background_color == "#FFFFFF"
    assert options.text_color == "#000000"


def test_dark_mode_swaps_the_whole_palette() -> None:
    """Flipping `dark_mode` replaces the palette, not just the background.

    The old `_apply_theme` recomputed `colors` by swapping `black` for
    `darkgrey` and left every other colour untouched; this fails if that
    single-substitution behaviour comes back.
    """
    options = PlotOptions()
    options.dark_mode = True
    assert options.palette is palette("dark")
    assert options.colors == list(palette("dark").series)
    assert options.background_color == "#000000"
    assert options.text_color == "#FFFFFF"


def test_dark_mode_is_reversible() -> None:
    """Setting `dark_mode` back to False restores the light palette exactly."""
    options = PlotOptions()
    original = list(options.colors)
    options.dark_mode = True
    options.dark_mode = False
    assert options.colors == original
    assert options.background_color == "#FFFFFF"


def test_dark_mode_setter_still_coerces_truthy_values() -> None:
    """`dark_mode = 1` behaves as `True` — the documented `int | bool` setter."""
    options = PlotOptions()
    options.dark_mode = 1
    assert options.dark_mode is True
    assert options.background_color == "#000000"


def test_dark_mode_colors_are_readable_on_the_dark_background() -> None:
    """The defect this extraction exists to fix.

    In the old dark mode, `colors` still held `purple` (2.2:1 on black) and
    `blue` (2.4:1) and the caller was expected to remember to reach for
    `lightcolors` instead. Nothing enforced that, and forgetting was silent.
    """
    options = PlotOptions()
    options.dark_mode = True
    too_faint = {
        color: round(contrast_ratio(color, options.background_color), 2)
        for color in options.colors
        if contrast_ratio(color, options.background_color) < MIN_CONTRAST_RATIO
    }
    assert not too_faint, f"unreadable dark-mode colours: {too_faint}"


@pytest.mark.parametrize("dark", [False, True])
def test_every_exposed_color_is_an_explicit_hex_string(dark: bool) -> None:
    """No attribute may hand back a matplotlib colour name.

    `_base_lightcolors` used to end with `"lightpurple"`, which does not
    resolve; storing hex removes the whole class of bug.
    """
    options = PlotOptions()
    options.dark_mode = dark
    exposed = [
        *options.colors,
        *options.lightcolors,
        options.background_color,
        options.text_color,
    ]
    offenders = [c for c in exposed if not HEX_RE.match(c)]
    assert not offenders, f"non-hex colours exposed: {offenders}"


@pytest.mark.parametrize("dark", [False, True])
def test_lightcolors_are_muted_counterparts_of_colors(dark: bool) -> None:
    """`lightcolors[i]` is a lower-contrast tint of `colors[i]`, same length.

    Fails if `lightcolors` degenerates into an alias for `colors` (no longer
    usable for fills behind a line) or drifts out of correspondence with it.
    """
    options = PlotOptions()
    options.dark_mode = dark
    assert len(options.lightcolors) == len(options.colors)
    for strong, muted in zip(options.colors, options.lightcolors, strict=True):
        assert muted != strong
        assert contrast_ratio(muted, options.background_color) < contrast_ratio(
            strong, options.background_color
        )


def test_mutating_colors_cannot_leak_into_the_next_instance() -> None:
    """The colour attributes hand out fresh lists, not the registry's tuples.

    Fails if the property returns a cached list: one caller appending to
    `options.colors` would then repaint every PlotOptions in the process.
    """
    first = PlotOptions()
    first.colors.append("#BADBAD")
    first.lightcolors.clear()
    second = PlotOptions()
    assert second.colors == list(palette("light").series)
    assert len(second.lightcolors) == len(second.colors)


def test_figure_geometry_stays_on_plot_options() -> None:
    """Geometry is not palette. It must survive the extraction untouched."""
    options = PlotOptions()
    assert options.myfigsize == (16, 9)
    assert options.fsize == 24
    assert options.dpi_choice == 300


def test_markers_and_linestyles_are_unchanged() -> None:
    """Marker and linestyle cycles are orthogonal to colour and stay as they were."""
    options = PlotOptions()
    assert options.markers == ["o", "s", "^", "v", "<", ">"]
    assert options.linestyles == ["solid", "dashed", "dashdot", "dotted"]


def test_plot_options_still_carries_the_base_options_fields() -> None:
    """`PlotOptions` remains an `Options` subclass with the inherited state."""
    options = PlotOptions()
    assert options.rawlog is False
    assert options.bugbear_choice is None
    assert hasattr(options, "home")
    assert hasattr(options, "args")
