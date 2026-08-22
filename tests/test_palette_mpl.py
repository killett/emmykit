"""The one matplotlib-facing piece of `emmykit.palette`: `Palette.rc_params`.

Split out from `test_palette.py` so the data-level invariants keep running in
an environment without matplotlib, which is an optional dependency.
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from matplotlib import colors as mcolors  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402

from emmykit.palette import Palette, palette, palette_names  # noqa: E402

# Exactly the rcParams the palette promises to set.
EXPECTED_KEYS = {
    "axes.prop_cycle",
    "figure.facecolor",
    "axes.facecolor",
    "savefig.facecolor",
    "text.color",
    "axes.labelcolor",
    "axes.edgecolor",
    "xtick.color",
    "ytick.color",
    "grid.color",
}


@pytest.fixture(params=list(palette_names()))
def pal(request: pytest.FixtureRequest) -> Palette:
    """Yield each registered palette in turn."""
    return palette(request.param)


def _all_colors(pal: Palette) -> list[str]:
    """Return every colour a palette carries: series colours plus roles."""
    return [*pal.series, pal.background, pal.foreground, pal.grid]


def test_every_color_resolves_through_matplotlib(pal: Palette) -> None:
    """`to_rgb` must accept every colour in every registered palette.

    This is the `lightpurple` regression test. `_base_lightcolors` used to end
    with `"lightpurple"`, which is in neither the CSS4 nor the base colour
    table, so `to_rgb` raised `ValueError` for any caller that reached the
    fifth series colour.
    """
    unresolvable = []
    for color in _all_colors(pal):
        try:
            mcolors.to_rgb(color)
        except ValueError as exc:
            unresolvable.append(f"{color}: {exc}")
    assert not unresolvable, f"{pal.name} palette: {unresolvable}"


def test_rc_params_sets_exactly_the_documented_keys(pal: Palette) -> None:
    """No key missing, no key extra.

    Fails if a role stops being wired up — e.g. dropping `savefig.facecolor`
    would silently save white-background PNGs from a dark figure.
    """
    assert set(pal.rc_params()) == EXPECTED_KEYS


def test_rc_params_maps_roles_onto_the_right_keys(pal: Palette) -> None:
    """Background, foreground and grid land where matplotlib expects them.

    Fails if `foreground` and `background` are ever transposed, which would
    make every label the same colour as the paper it is printed on.
    """
    rc = pal.rc_params()
    assert rc["figure.facecolor"] == pal.background
    assert rc["axes.facecolor"] == pal.background
    assert rc["savefig.facecolor"] == pal.background
    assert rc["text.color"] == pal.foreground
    assert rc["axes.labelcolor"] == pal.foreground
    assert rc["axes.edgecolor"] == pal.foreground
    assert rc["xtick.color"] == pal.foreground
    assert rc["ytick.color"] == pal.foreground
    assert rc["grid.color"] == pal.grid


def test_prop_cycle_carries_the_series_in_order(pal: Palette) -> None:
    """`axes.prop_cycle` is a colour cycler over exactly `series`, in order."""
    cycle = pal.rc_params()["axes.prop_cycle"]
    assert [entry["color"] for entry in cycle] == list(pal.series)


def test_rc_params_is_accepted_by_rc_context(pal: Palette) -> None:
    """Every key is a real rcParam and every value validates.

    `rc_context` raises `KeyError` on an unknown rcParam name and `ValueError`
    on an unparseable value, so a typo like `axes.facecolour` fails here
    rather than being silently ignored at plot time.
    """
    with plt.rc_context(pal.rc_params()):
        assert matplotlib.rcParams["axes.facecolor"] == pal.background


def test_artists_inherit_the_theme_without_naming_a_color(pal: Palette) -> None:
    """The acceptance case: open an rc_context, plot, get themed output.

    Fails if the bridge stops applying — the first line would come out
    matplotlib's default `#1f77b4` and the figure would keep the default
    white face.
    """
    with plt.rc_context(pal.rc_params()):
        fig, ax = plt.subplots()
        (line,) = ax.plot([0, 1], [0, 1])
        try:
            assert mcolors.to_rgba(line.get_color()) == mcolors.to_rgba(
                pal.series[0]
            )
            assert fig.get_facecolor() == mcolors.to_rgba(pal.background)
            assert ax.get_facecolor() == mcolors.to_rgba(pal.background)
        finally:
            plt.close(fig)


def test_more_lines_than_colors_wraps_rather_than_failing(pal: Palette) -> None:
    """Plotting past the end of the cycle wraps to the start.

    matplotlib's documented behaviour, pinned here so a future palette change
    cannot turn "more series than colours" into an exception or a silent drop
    to a single colour.
    """
    count = len(pal.series)
    with plt.rc_context(pal.rc_params()):
        fig, ax = plt.subplots()
        try:
            lines = [ax.plot([0, 1], [n, n])[0] for n in range(count + 2)]
            colors = [mcolors.to_rgba(line.get_color()) for line in lines]
        finally:
            plt.close(fig)
    assert colors[count] == colors[0]
    assert colors[count + 1] == colors[1]
    assert len(set(colors[:count])) == count


def test_rc_params_returns_an_independent_mapping_each_call() -> None:
    """One caller mutating the returned mapping cannot affect the next.

    Fails if `rc_params` caches and returns one shared dict, or hands out the
    palette's own `series` list object inside the cycler.
    """
    pal = palette("dark")
    first = pal.rc_params()
    first["figure.facecolor"] = "#BADBAD"
    first["axes.prop_cycle"] = None
    second = pal.rc_params()
    assert second["figure.facecolor"] == pal.background
    assert [entry["color"] for entry in second["axes.prop_cycle"]] == list(
        pal.series
    )
