"""`emmykit.datetime_utils` behaviour that doesn't need matplotlib installed.

Kept apart from `test_datetime_utils_mpl.py`, which skips as a whole without
matplotlib, so these keep running in an install without the `datetime` extra.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from emmykit.datetime_utils import (
    decimal_year_to_datetime,
    extract_timestamp,
    parse_datetime,
    parse_timezone,
)
from tests._helpers import run_python

UTC = dt.timezone.utc


@pytest.mark.parametrize(
    ("tz_arg", "expected"),
    [
        (None, UTC),
        ("Z", UTC),
        ("utc", UTC),
        (" GMT ", UTC),
        ("UTC+05:30", dt.timezone(dt.timedelta(hours=5, minutes=30))),
        ("GMT-4", dt.timezone(dt.timedelta(hours=-4))),
        ("+0200", dt.timezone(dt.timedelta(hours=2))),
        ("EST", ZoneInfo("America/New_York")),
        ("America/Chicago", ZoneInfo("America/Chicago")),
        (UTC, UTC),
    ],
)
def test_parse_timezone_accepts_each_documented_form(tz_arg: object, expected: dt.tzinfo) -> None:
    """Names, abbreviations, UTC/GMT with or without an offset, and tzinfo objects."""
    assert parse_timezone(tz_arg) == expected


def test_parse_timezone_passes_naive_through() -> None:
    """ "Naive" is returned as given, for the caller to strip the zone."""
    assert parse_timezone("Naive") == "Naive"


def test_parse_timezone_rejects_an_unknown_name() -> None:
    """A string that's no zone, abbreviation or offset is a ValueError."""
    with pytest.raises(ValueError):
        parse_timezone("Not/AZone")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("run_20240101-123456.pkl", "20240101-123456"), ("no stamp here.pkl", None)],
)
def test_extract_timestamp(text: str, expected: str | None) -> None:
    """A YYYYMMDD-HHMMSS stamp before ".pkl" is returned; otherwise None."""
    assert extract_timestamp(text) == expected


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


def test_decimal_year_works_in_year_9999() -> None:
    """Halfway through 9999 (365 days) is noon on 2 July. Fails if 1 January 10000 is built."""
    assert decimal_year_to_datetime(9999.5).isoformat() == "9999-07-02T12:00:00+00:00"


@pytest.mark.parametrize("dec", [float("inf"), 1e10, float("nan")])
def test_decimal_year_out_of_range_is_a_value_error(dec: float) -> None:
    """Years datetime can't hold raise ValueError, never OverflowError."""
    with pytest.raises(ValueError, match="Failed to convert decimal year"):
        decimal_year_to_datetime(dec)


def test_parse_datetime_of_a_huge_number_is_a_value_error() -> None:
    """"1e10" is read as a decimal year, which is out of range: a ValueError, as documented."""
    with pytest.raises(ValueError):
        parse_datetime("1e10")


def test_extract_timestamp_needs_a_literal_dot_before_pkl() -> None:
    """Fails if the '.' in the pattern matches any character."""
    assert extract_timestamp("run_20240101-123456xpkl") is None


def test_parse_timezone_ignores_surrounding_spaces_in_a_zone_name() -> None:
    """Abbreviations are already stripped; full zone names must be too."""
    assert parse_timezone(" America/New_York ") == ZoneInfo("America/New_York")
