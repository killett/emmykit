"""palette — colourblind-safe figure palettes, independent of any options bag.

A palette is *data*: an ordered tuple of qualitative series colours plus the
three semantic roles a figure needs (background, foreground, grid). Nothing in
this module imports matplotlib at module scope — code that only wants hex
strings pays nothing for the plotting stack. `Palette.rc_params` imports it
lazily, on the one call that genuinely needs it.

Every colour is stored as an explicit ``#RRGGBB`` string rather than a
matplotlib colour name. Names are a trap: ``lightpurple`` reads perfectly
plausibly and is in neither the CSS4 nor the base colour table, so
``matplotlib.colors.to_rgb`` raises ``ValueError`` the moment a caller reaches
that entry of the cycle.

The series colours derive from the Okabe-Ito qualitative set, which is designed
to stay distinguishable under the common forms of colour vision deficiency.
Per-theme readability is obtained by shifting luminance toward or away from the
background until each colour clears `MIN_CONTRAST_RATIO`, rather than by
picking replacements by eye.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "MIN_CONTRAST_RATIO",
    "Palette",
    "contrast_ratio",
    "palette",
    "palette_names",
]

MIN_CONTRAST_RATIO: Final[float] = 4.5
"""WCAG 2.1 AA contrast minimum for normal-size text, applied here to every
series colour against its own palette's background. A line the reader cannot
follow is a line that was not plotted."""

# The Okabe-Ito eight, minus black (a background/foreground role here, and
# invisible on the dark palette) and minus yellow (#F0E442, which converges on
# the darkened orange once both are forced to clear the contrast minimum
# against white). Six distinct hues remain, none of them a red/green pair.
_OKABE_ITO: Final[tuple[str, ...]] = (
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
)

_HEX_RE: Final[re.Pattern[str]] = re.compile(r"\A#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})\Z")

_WHITE: Final[str] = "#FFFFFF"
_BLACK: Final[str] = "#000000"


def _parse_hex(color: str) -> tuple[int, int, int]:
    """Split a hex colour string into its three 0-255 channels.

    Args:
        color: A ``#RGB`` or ``#RRGGBB`` string. Case-insensitive.

    Returns:
        The red, green and blue channels as integers in ``0..255``.

    Raises:
        ValueError: If `color` is not a hex string of one of those two
            lengths. Colour *names* land here deliberately: this module
            stores hex only.
    """
    if not isinstance(color, str) or not _HEX_RE.match(color):
        raise ValueError(
            f"not a hex colour: {color!r}; expected '#RGB' or '#RRGGBB'"
        )
    digits = color[1:]
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def _format_hex(channels: tuple[int, int, int]) -> str:
    """Render three 0-255 channels as an uppercase ``#RRGGBB`` string.

    Args:
        channels: Red, green and blue as integers in ``0..255``.

    Returns:
        The canonical uppercase hex form of that colour.
    """
    red, green, blue = channels
    return f"#{red:02X}{green:02X}{blue:02X}"


def _linearize(channel: int) -> float:
    """Undo the sRGB transfer function for one 0-255 channel.

    Args:
        channel: A single colour channel in ``0..255``.

    Returns:
        The linear-light value of that channel in ``0.0..1.0``.
    """
    fraction = channel / 255.0
    if fraction <= 0.04045:
        return fraction / 12.92
    return ((fraction + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> float:
    """Compute the WCAG relative luminance of a hex colour.

    Args:
        color: A ``#RGB`` or ``#RRGGBB`` string.

    Returns:
        Relative luminance in ``0.0`` (black) to ``1.0`` (white).

    Raises:
        ValueError: If `color` is not a hex colour string.
    """
    red, green, blue = (_linearize(c) for c in _parse_hex(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(color: str, background: str) -> float:
    """Return the WCAG contrast ratio between two colours.

    The ratio is symmetric and ranges from ``1.0`` (identical colours) to
    ``21.0`` (black against white). WCAG 2.1 AA asks for at least ``4.5`` for
    normal text; `MIN_CONTRAST_RATIO` carries that threshold.

    Args:
        color: Foreground colour as a ``#RGB`` or ``#RRGGBB`` string.
        background: Background colour, same format.

    Returns:
        The contrast ratio, ``(lighter + 0.05) / (darker + 0.05)``.

    Raises:
        ValueError: If either argument is not a hex colour string.

    Example:
        >>> round(contrast_ratio("#FFFFFF", "#000000"), 1)
        21.0
    """
    first = _relative_luminance(color)
    second = _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _mix(color: str, toward: str, fraction: float) -> str:
    """Blend a colour toward another in sRGB space.

    Args:
        color: The starting colour, ``#RGB`` or ``#RRGGBB``.
        toward: The colour to blend toward, same format.
        fraction: How far to travel, ``0.0`` (unchanged) to ``1.0`` (`toward`).

    Returns:
        The blended colour as an uppercase ``#RRGGBB`` string.
    """
    start = _parse_hex(color)
    end = _parse_hex(toward)
    blended = tuple(
        round(s + (e - s) * fraction) for s, e in zip(start, end, strict=True)
    )
    return _format_hex(blended)  # type: ignore[arg-type]


def _shift_to_contrast(
    color: str, background: str, toward: str, minimum: float
) -> str:
    """Blend a colour toward `toward` until it clears `minimum` on `background`.

    Colours already clearing the threshold are returned untouched, so the
    Okabe-Ito values survive verbatim wherever they are already readable. The
    search walks in 1/255 steps — the smallest step an 8-bit channel can
    express — and so is deterministic and terminates in at most 256 rounds.

    Args:
        color: The colour to adjust, ``#RRGGBB``.
        background: The background it must be readable against.
        toward: ``#FFFFFF`` to lighten, ``#000000`` to darken.
        minimum: The contrast ratio to reach.

    Returns:
        The adjusted colour, or `color` itself if it already qualified.

    Raises:
        ValueError: If no blend fraction reaches `minimum`, which means
            `toward` was chosen on the same side of the background as
            `color`.
    """
    steps = 255
    for step in range(steps + 1):
        candidate = _mix(color, toward, step / steps)
        if contrast_ratio(candidate, background) >= minimum:
            return candidate
    raise ValueError(
        f"cannot reach {minimum}:1 for {color!r} on {background!r} "
        f"by blending toward {toward!r}"
    )


@dataclass(frozen=True, slots=True)
class Palette:
    """An immutable figure theme: qualitative series colours plus semantic roles.

    Attributes:
        name: The key this palette is registered under.
        series: Ordered qualitative colours for successive data series, as
            uppercase ``#RRGGBB`` strings. Every one of them clears
            `MIN_CONTRAST_RATIO` against `background`.
        background: Figure and axes face colour.
        foreground: Text, tick, label and spine colour.
        grid: Grid-line colour — decoration, deliberately lower contrast than
            `foreground`.
    """

    name: str
    series: tuple[str, ...]
    background: str
    foreground: str
    grid: str

    def rc_params(self) -> dict[str, Any]:
        """Return a matplotlib rcParams mapping expressing this palette.

        Intended for ``with plt.rc_context(palette.rc_params()):`` — inside
        that block every artist inherits the theme and the caller never names
        a colour. The returned mapping is a fresh object on every call, so
        mutating it cannot affect the registry or another caller.

        Returns:
            A mapping from rcParam name to value, setting ``axes.prop_cycle``
            from `series` and the figure/axes/text/tick/grid colours from the
            roles.

        Raises:
            ImportError: If matplotlib is not installed. It is an optional
                dependency; the rest of this module is stdlib-only.
        """
        from cycler import cycler

        return {
            "axes.prop_cycle": cycler(color=list(self.series)),
            "figure.facecolor": self.background,
            "axes.facecolor": self.background,
            "savefig.facecolor": self.background,
            "text.color": self.foreground,
            "axes.labelcolor": self.foreground,
            "axes.edgecolor": self.foreground,
            "xtick.color": self.foreground,
            "ytick.color": self.foreground,
            "grid.color": self.grid,
        }


def _build(name: str, background: str, foreground: str, grid: str) -> Palette:
    """Assemble one themed palette from the Okabe-Ito base.

    Each base colour is shifted away from `background` — darkened on a light
    theme, lightened on a dark one — only as far as `MIN_CONTRAST_RATIO`
    requires.

    Args:
        name: The registry key for this palette.
        background: Figure background, ``#RRGGBB``.
        foreground: Text/tick/spine colour, ``#RRGGBB``.
        grid: Grid-line colour, ``#RRGGBB``.

    Returns:
        The assembled `Palette`.
    """
    toward = _BLACK if _relative_luminance(background) > 0.5 else _WHITE
    series = tuple(
        _shift_to_contrast(color, background, toward, MIN_CONTRAST_RATIO)
        for color in _OKABE_ITO
    )
    return Palette(
        name=name,
        series=series,
        background=background,
        foreground=foreground,
        grid=grid,
    )


_PALETTES: Final[dict[str, Palette]] = {
    "light": _build("light", background=_WHITE, foreground=_BLACK, grid="#CCCCCC"),
    "dark": _build("dark", background=_BLACK, foreground=_WHITE, grid="#333333"),
}


def palette_names() -> tuple[str, ...]:
    """Return the names of every registered palette, in registration order.

    Returns:
        The registry keys, suitable for offering to a user as choices.
    """
    return tuple(_PALETTES)


def palette(name: str) -> Palette:
    """Look up a registered palette by name.

    Args:
        name: A registered palette name — see `palette_names`.

    Returns:
        The shared, frozen `Palette` for that name. Repeated lookups return
        the same instance; it cannot be mutated, so sharing is safe.

    Raises:
        ValueError: If `name` is not registered. The message lists the names
            that are.

    Example:
        >>> palette("dark").background
        '#000000'
    """
    try:
        return _PALETTES[name]
    except KeyError:
        registered = ", ".join(repr(key) for key in _PALETTES)
        raise ValueError(
            f"unknown palette {name!r}; registered palettes are: {registered}"
        ) from None
