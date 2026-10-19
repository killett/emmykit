"""`emmykit.hosts`: the computer-name constants computed at import."""

from __future__ import annotations

import emmykit
from tests._helpers import run_python


def test_importing_emmykit_leaves_logging_unconfigured() -> None:
    """After `import emmykit` the caller's own `logging.basicConfig()` still works.

    Fails if computing COMPUTER_NAME at import installs a root handler, which
    turns every later `basicConfig()` in the caller's program into a no-op.
    """
    result = run_python(
        "import logging\n"
        "import emmykit\n"
        "root = logging.getLogger()\n"
        "print(len(root.handlers), logging.getLevelName(root.level))\n"
        "logging.basicConfig(level=logging.DEBUG)\n"
        "print(logging.getLevelName(root.level))\n"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["0", "WARNING", "DEBUG"]


def test_computer_name_constant_matches_a_fresh_lookup() -> None:
    """The constant is the same name `get_computer_name` finds when called now."""
    assert emmykit.COMPUTER_NAME == emmykit.get_computer_name(rawlog=True)
    assert emmykit.IS_NASA_COMPUTER == emmykit.COMPUTER_NAME.casefold().startswith(
        emmykit.NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES
    )
