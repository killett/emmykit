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


@pytest.mark.parametrize(
    ("given", "timezone", "expected"),
    [
        ("Tue, 25 Jun 2025 14:00:00 EST", None, "2025-06-25T19:00:00+00:00"),
        ("2025-06-25 14:00:00 UTC", NY, "2025-06-25T10:00:00-04:00"),
        ("Tue, 25 Jun 2025 14:00:00 GMT", NY, "2025-06-25T10:00:00-04:00"),
    ],
)
def test_named_zone_in_the_text_is_converted(given: str, timezone: str | None, expected: str) -> None:
    """A zone name the parser understands makes the time aware, so it's converted.

    Fails if only a trailing Z or numeric offset counts, and the parsed EST or
    UTC is overwritten with the target zone instead.
    """
    assert parse_datetime(given, timezone=timezone).isoformat() == expected


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("2002", "2002-01-01T00:00:00-05:00"),
        (2002, "2002-01-01T00:00:00-05:00"),
        (2002.0, "2002-01-01T00:00:00-05:00"),
        (2002.5, "2002-07-02T12:00:00-04:00"),
    ],
)
def test_year_is_read_in_the_target_zone(given: str | float, expected: str) -> None:
    """A year means midnight on 1 January in the target zone, like "2002-10" does.

    Fails if the year is taken as a UTC instant and converted, which puts
    "2002" in New York at 19:00 on 31 December 2001.
    """
    assert parse_datetime(given, timezone=NY).isoformat() == expected


def test_epoch_given_as_a_year_is_midnight_in_the_target_zone() -> None:
    """ "days since 2000" counts from midnight on 1 January 2000 in the target zone."""
    result = parse_datetime(1, timezone=NY, format_str="days since 2000")
    assert result.isoformat() == "2000-01-02T00:00:00-05:00"


def test_trailing_year_is_not_mistaken_for_an_offset() -> None:
    """ "-2002" at the end is a year, so the result is midnight UTC on any host.

    Fails under one of the two host timezones if the date is treated as having
    an offset and its naive value is then read in local time.
    """
    assert parse_datetime("18-Oct-2002").isoformat() == "2002-10-18T00:00:00+00:00"


def test_forced_conversion_reads_a_naive_value_as_utc() -> None:
    """should_convert=True on a bare wall time converts from UTC, not from local time."""
    result = parse_datetime(dt.datetime(2002, 10, 18, 7), timezone=NY, should_convert=True)
    assert result.isoformat() == "2002-10-18T03:00:00-04:00"


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


@pytest.mark.parametrize(
    ("tz", "timezone", "expected"),
    [(None, None, "2002-10-18T07:00:00+00:00"), ("UTC", NY, "2002-10-18T03:00:00-04:00")],
)
def test_pandas_timestamp_keeps_its_time_and_zone(
    tz: str | None, timezone: str | None, expected: str
) -> None:
    """The docstring's own example: a Timestamp keeps its time of day.

    Fails if the Timestamp, a `datetime.date` subclass, is taken for a plain
    date and cut to midnight with its zone dropped.
    """
    pd = pytest.importorskip("pandas")
    stamp = pd.Timestamp("2002-10-18 07:00:00", tz=tz)
    assert parse_datetime(stamp, timezone=timezone).isoformat() == expected


def test_numpy_datetime64_with_naive_target_keeps_its_utc_wall_time() -> None:
    """ "Naive" gives the datetime64's own (UTC) wall time on any host.

    Fails under both host timezones if the timestamp is turned into local time.
    """
    np = pytest.importorskip("numpy")
    result = parse_datetime(np.datetime64("2002-10-18T07:00"), timezone="Naive")
    assert result.isoformat() == "2002-10-18T07:00:00"


def test_unparseable_string_raises_value_error() -> None:
    """A string no parser understands is a ValueError naming it."""
    with pytest.raises(ValueError, match="garbage!!"):
        parse_datetime("garbage!!")


def test_unparseable_epoch_raises_value_error_naming_it() -> None:
    """A bad epoch in the format string is a ValueError that quotes it.

    Fails with UnboundLocalError if the message refers to the epoch that failed
    to parse instead of the text it came from.
    """
    with pytest.raises(ValueError, match="Invalid epoch 'notadate'"):
        parse_datetime(5, format_str="days since notadate")


def test_unsupported_type_raises_type_error() -> None:
    """An object that isn't a date of any kind is a TypeError."""
    with pytest.raises(TypeError):
        parse_datetime(object())  # type: ignore[arg-type]
