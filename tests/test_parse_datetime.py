"""`parse_datetime`: what each kind of input becomes, in UTC and in another zone.

Every test runs twice, under host timezones on either side of UTC, so a result
that depends on the machine's local time fails one of the two runs. Expected
values are ISO strings worked out by hand; New York is UTC-4 on 2002-10-18
(daylight time) and UTC-5 in January.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from collections.abc import Iterator

import pytest

pytest.importorskip("dateutil")

from emmykit.datetime_utils import parse_datetime  # noqa: E402

NY = "America/New_York"
UTC = dt.timezone.utc


@pytest.fixture(autouse=True, params=["America/Los_Angeles", "Asia/Tokyo"])
def host_timezone(request: pytest.FixtureRequest) -> Iterator[str]:
    """Run the test with the process's local timezone set to each param in turn."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    yield request.param
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


@pytest.mark.parametrize(
    ("given", "timezone", "expected"),
    [
        ("2002-10-18T07:00:00Z", None, "2002-10-18T07:00:00+00:00"),
        ("2002-10-18T07:00:00Z", NY, "2002-10-18T03:00:00-04:00"),
        ("2002-10-18T07:00:00+02:00", None, "2002-10-18T05:00:00+00:00"),
        ("2002-10-18", None, "2002-10-18T00:00:00+00:00"),
        ("2002-10-18", NY, "2002-10-18T00:00:00-04:00"),
        ("2002-10", None, "2002-10-01T00:00:00+00:00"),
        ("18 Oct 2002", None, "2002-10-18T00:00:00+00:00"),
        ("JD 2451545.0", None, "2000-01-01T12:00:00+00:00"),
        ("MJD 51544.5", None, "2000-01-01T12:00:00+00:00"),
        ("J2000", None, "2000-01-01T11:58:55.816000+00:00"),
        ("UNIX", NY, "1969-12-31T19:00:00-05:00"),
        (2002.0, None, "2002-01-01T00:00:00+00:00"),
        (2002.5, None, "2002-07-02T12:00:00+00:00"),
        (dt.datetime(2002, 10, 18, 7), NY, "2002-10-18T07:00:00-04:00"),
        (dt.datetime(2002, 10, 18, 7, tzinfo=UTC), NY, "2002-10-18T03:00:00-04:00"),
        (dt.date(2002, 10, 18), None, "2002-10-18T00:00:00+00:00"),
    ],
)
def test_input_kinds(given: object, timezone: str | None, expected: str) -> None:
    """A zone in the input is converted; a bare wall time takes the target zone."""
    assert parse_datetime(given, timezone=timezone).isoformat() == expected


@pytest.mark.parametrize(
    ("given", "format_str", "expected"),
    [
        (86400, "seconds", "1970-01-02T00:00:00+00:00"),
        (1, "days since 2000-01-01", "2000-01-02T00:00:00+00:00"),
        (1.5, "hours after 2000-01-01T00:00:00Z", "2000-01-01T01:30:00+00:00"),
    ],
)
def test_count_of_units_since_an_epoch(given: float, format_str: str, expected: str) -> None:
    """A number with a "units since epoch" format is that much time after the epoch."""
    assert parse_datetime(given, format_str=format_str).isoformat() == expected


def test_should_convert_false_attaches_instead_of_converting() -> None:
    """The override keeps the wall time and swaps in the target zone."""
    result = parse_datetime("2002-10-18T07:00:00Z", timezone=NY, should_convert=False)
    assert result.isoformat() == "2002-10-18T07:00:00-04:00"


def test_naive_target_keeps_the_written_wall_time() -> None:
    """ "Naive" drops the zone without converting."""
    result = parse_datetime("2002-10-18T07:00:00+02:00", timezone="Naive")
    assert result.isoformat() == "2002-10-18T07:00:00"


@pytest.mark.parametrize(
    ("timezone", "expected"),
    [(None, "2002-10-18T07:00:00+00:00"), (NY, "2002-10-18T03:00:00-04:00")],
)
def test_numpy_datetime64_is_read_as_utc(timezone: str | None, expected: str) -> None:
    """A datetime64 counts from the Unix epoch in UTC, so it is converted like an instant."""
    np = pytest.importorskip("numpy")
    assert parse_datetime(np.datetime64("2002-10-18T07:00"), timezone=timezone).isoformat() == expected


def test_unparseable_string_raises_value_error() -> None:
    """A string no parser understands is a ValueError naming it."""
    with pytest.raises(ValueError, match="garbage!!"):
        parse_datetime("garbage!!")


def test_unsupported_type_raises_type_error() -> None:
    """An object that isn't a date of any kind is a TypeError."""
    with pytest.raises(TypeError):
        parse_datetime(object())  # type: ignore[arg-type]
