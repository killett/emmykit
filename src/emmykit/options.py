"""options — extracted from univ_defs.py."""

from __future__ import annotations

import logging
from pathlib import Path

class Options:
    """Class that has all global options in one place."""

    def __init__(self) -> None:
        """Initialize the options with default values."""
        import argparse
        self.log_mode:                      int = logging.INFO
        self.home:                         Path = Path.home()  # User's home directory
        self.shell:                  str | None = None
        self.rc_file:               Path | None = None
        self.alias:                  str | None = None  # The alias to use for this script, if any.
        self.alias_command:          str | None = None  # The command to run when the alias is used.
        self.additional_alias_files: list[Path] = []
        self.rawlog:                       bool = False
        self.bugbear_choice:         str | None = None  # set by run_flake8() if bugbear is installed.
        self.args:           argparse.Namespace = argparse.Namespace()

class PlotOptions(Options):
    """Global figure options."""

    def __init__(self) -> None:
        """Initialize PlotOptions class with values from the Options class, and default plotting values."""
        # Ideas for improving this parent class: https://chatgpt.com/share/6876a7e2-da84-8006-9c8f-100d243b73e4
        super().__init__()
        self.myfigsize  = (16, 9)
        self.fsize      = 24
        self.dpi_choice = 300
        # keep immutable "base" palettes so we can recompute safely
        self._base_colors      = ["black", "red",    "blue",      "green",      "purple"]
        self._base_lightcolors = ["grey",  "pink",   "lightblue", "lightgreen", "lightpurple"]
        self.markers           = ["o",     "s",      "^",         "v",          "<",          ">"]
        self.linestyles        = ["solid", "dashed", "dashdot",   "dotted"]

        self._dark_mode = False   # backing store
        self._apply_theme()       # derive palettes/background/text from _dark_mode

    @property
    def dark_mode(self) -> bool:
        """This is a property, so setting it will also update the theme."""
        return self._dark_mode

    @dark_mode.setter
    def dark_mode(self, value: int | bool) -> None:
        """This is a property with a setter, so any child class that changes self.dark_mode will also update the theme."""
        self._dark_mode = bool(value)
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply the current theme (light or dark) to the plot options."""
        if self._dark_mode:
            self.background_color = "#000000"
            self.text_color       = "#FFFFFF"
            # recompute "view" palettes from the bases
            self.colors      = [ ("darkgrey" if  c == "black" else c) for c in self._base_colors ]
            self.lightcolors = [ ("lightgrey" if c == "grey"  else c) for c in self._base_lightcolors ]
        else:
            self.background_color = "#FFFFFF"
            self.text_color       = "#000000"
            self.colors      = list(self._base_colors)
            self.lightcolors = list(self._base_lightcolors)
