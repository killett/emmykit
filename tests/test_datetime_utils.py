"""`emmykit.datetime_utils` behaviour that doesn't need matplotlib installed.

Kept apart from `test_datetime_utils_mpl.py`, which skips as a whole without
matplotlib, so these keep running in an install without the `datetime` extra.
"""

from __future__ import annotations

from tests._helpers import run_python


def test_missing_matplotlib_raises_import_error_naming_the_extra() -> None:
    """Without matplotlib, emmykit imports and construction says what to install.

    A `None` entry in `sys.modules` makes every `import matplotlib...` fail,
    standing in for an install without the `datetime` extra. Fails if
    construction surfaces matplotlib's bare `ModuleNotFoundError`, which says
    nothing about emmykit's extras, or if the original error is not chained
    on, hiding the real cause when matplotlib is installed but broken.
    """
    result = run_python(
        "import sys\n"
        "sys.modules['matplotlib'] = None\n"
        "import emmykit\n"
        "try:\n"
        "    emmykit.AdaptiveDateFormatter()\n"
        "except ImportError as exc:\n"
        "    print(type(exc).__name__, exc, type(exc.__cause__).__name__, sep='|')\n"
        "else:\n"
        "    print('constructed without matplotlib')\n"
    )

    assert result.returncode == 0, result.stderr
    name, message, cause = result.stdout.strip().split("|")
    assert name == "ImportError"
    assert "emmykit[datetime]" in message
    assert cause == "ModuleNotFoundError"
