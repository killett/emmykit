"""options — extracted from univ_defs.py."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

# `_mix` is private to `palette` because a palette is a closed set of four
# public pieces; `lightcolors` is a compatibility concern of *this* layer, so
# the tinting happens here rather than widening the palette API.
from emmykit.palette import Palette, _mix, palette

# How far a `lightcolors` entry is blended toward the background. Half-way is
# enough to read as a fill behind its full-strength counterpart without
# vanishing into the paper.
_TINT_FRACTION: Final[float] = 0.5

class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the options with default values."""
        import argparse
        self.log_mode:                      int = logging.INFO
        self.home:                         Path = Path.home()  # User's home directory
        self.rawlog:                       bool = False
        self.bugbear_choice:         str | None = None  # set by run_flake8() if bugbear is installed.
        self.args:           argparse.Namespace = argparse.Namespace()

class PlotOptions(Options):
    """Global figure options.

    Colour lives in `emmykit.palette` and is reached through the `palette`
    attribute; the `colors` / `lightcolors` / `background_color` / `text_color`
    attributes remain as read-only views onto it, so existing callers are
    unaffected. Figure geometry (`myfigsize`, `fsize`, `dpi_choice`) and the
    marker/linestyle cycles stay here — they are not colour.
    """

    def __init__(self) -> None:
        """Initialize PlotOptions class with values from the Options class, and default plotting values."""
        super().__init__()
        self.myfigsize  = (16, 9)
        self.fsize      = 24
        self.dpi_choice = 300
        self.markers    = ["o",     "s",      "^",       "v",      "<", ">"]
        self.linestyles = ["solid", "dashed", "dashdot", "dotted"]

        self._dark_mode = False              # backing store
        self._palette   = palette("light")   # derived from _dark_mode

    @property
    def palette(self) -> Palette:
        """The `Palette` backing every colour attribute on this instance.

        Returns:
            The frozen palette for the current theme. Pass its `rc_params()`
            to `matplotlib.pyplot.rc_context` to theme a whole figure.
        """
        return self._palette

    @property
    def dark_mode(self) -> bool:
        """Whether the dark theme is active.

        Returns:
            True when the dark palette is selected.
        """
        return self._dark_mode

    @dark_mode.setter
    def dark_mode(self, value: int | bool) -> None:
        """Select the light or dark palette.

        Assigning here swaps the whole palette, so every colour attribute
        follows in one step — including in a child class that sets
        `self.dark_mode`.

        Args:
            value: Truthy for the dark theme, falsy for the light one.
        """
        self._dark_mode = bool(value)
        self._palette   = palette("dark" if self._dark_mode else "light")

    @property
    def colors(self) -> list[str]:
        """Qualitative series colours for the current theme.

        Returns:
            A fresh list of ``#RRGGBB`` strings, every one of them readable
            against `background_color`. Mutating the returned list does not
            affect this instance or any other.
        """
        return list(self._palette.series)

    @property
    def lightcolors(self) -> list[str]:
        """Muted counterparts of `colors`, for fills behind their own series.

        Returns:
            A fresh list of ``#RRGGBB`` strings, positionally matching
            `colors`, each blended half-way toward `background_color`.
        """
        background = self._palette.background
        return [_mix(color, background, _TINT_FRACTION)
                for color in self._palette.series]

    @property
    def background_color(self) -> str:
        """Figure background colour for the current theme.

        Returns:
            The palette's background as a ``#RRGGBB`` string.
        """
        return self._palette.background

    @property
    def text_color(self) -> str:
        """Text, tick and spine colour for the current theme.

        Returns:
            The palette's foreground as a ``#RRGGBB`` string.
        """
        return self._palette.foreground
