"""datetime_utils — extracted from univ_defs.py."""

from __future__ import annotations

import functools
import logging
import re

from emmykit.inflect_utils import my_plural
from emmykit.logging_utils import fallback_logging_config
from emmykit.numeric_helpers import is_float, seconds_in_unit

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final, TypeAlias

def human_timespan(timespan: int | float) -> str:
    """
    Format a time span in seconds into a human-readable string.
    Negative values are treated as absolute.

    Args:
        timespan: A float or int representing the time span in seconds.

    Returns:
        A human-readable string describing the time span, such as
        "1 year, 2 weeks, 3 days, 4 hours, 5 minutes and 6.789 seconds".
        If the timespan is zero, returns "0 seconds".

    Raises:
        ValueError:    If timespan is not a number, or is NaN.
        OverflowError: If timespan is infinite.
    """
    # Work in integer milliseconds to avoid float modulo issues
    total_ms = int(round(abs(float(timespan)) * 1000))
    if total_ms == 0:
        return "0 seconds"

    MS_PER_MINUTE =         60_000
    MS_PER_HOUR   =      3_600_000
    MS_PER_DAY    =     86_400_000
    MS_PER_WEEK   =    604_800_000
    MS_PER_YEAR   = 31_557_600_000  # 365.25 days

    components: list[str] = []

    years, rem   = divmod(total_ms, MS_PER_YEAR)
    weeks, rem   = divmod(rem,      MS_PER_WEEK)
    days,  rem   = divmod(rem,      MS_PER_DAY)
    hours, rem   = divmod(rem,      MS_PER_HOUR)
    minutes, rem = divmod(rem,      MS_PER_MINUTE)
    seconds = rem / 1000.0  # in [0, 60)

    if years:   components.append(my_plural(years,     "year"))
    if weeks:   components.append(my_plural(weeks,     "week"))
    if days:    components.append(my_plural(days,       "day"))
    if hours:   components.append(my_plural(hours,     "hour"))
    if minutes: components.append(my_plural(minutes, "minute"))
    if seconds:
        s = f"{seconds:.3f}".rstrip("0").rstrip(".")
        components.append(f"{s} second" + ("" if seconds == 1.0 else "s"))

    if len(components) == 1:
        return components[0]
    return ", ".join(components[:-1]) + " and " + components[-1]

def format_date_range(date1: dt.datetime, date2: dt.datetime | None = None) -> str:
    """
    Process a pair of datetime.datetime dates and produce a formatted date range string
    where each date looks like 'Jan  7, 2025'. If date2 is not provided, it is set to date1.

    Args:
        date1: The first date as a datetime.datetime object.
        date2: The second date as a datetime.datetime object. If None, defaults to date1.

    Returns:
        A formatted string representing the date range, such as 'Jan  7, 2025' or 'Jan  7 - Feb  3, 2025' or 'Jan  7 - 15, 2025'.
        If both dates and times are the same, it returns just one date like 'Jan  7, 2025'.
        If both dates are the same but times are different, it returns a string like '06:04:02 - 19:05:39 on Jan  7, 2025'

    Raises:
        ValueError: If either date1 or date2 is not a datetime.datetime object.
    """
    import datetime as dt

    month_names = {
        1: "Jan",  2: "Feb",  3: "Mar",  4: "Apr",
        5: "May",  6: "Jun",  7: "Jul",  8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }

    # If date2 is not provided, set date2 to date1
    if date2 is None:
        date2 = date1

    # Make sure both dates are datetime.datetime objects
    if not isinstance(date1, dt.datetime) or not isinstance(date2, dt.datetime):
        raise ValueError(f"Both dates must be datetime.datetime objects, but date1 is {date1} with type {type(date1)} and date2 {date2} with type {type(date2)}.")

    # Ensure that the first date is earlier than the second.
    if date1 > date2:
        date1, date2 = date2, date1

    day1, day2     = date1.day, date2.day
    month1, month2 = month_names[date1.month], month_names[date2.month]
    year1, year2   = date1.year, date2.year

    if year1 == year2:
        if month1 == month2:
            if day1 == day2:
                time1 = date1.strftime("%H:%M:%S")
                time2 = date2.strftime("%H:%M:%S")
                if time1 == time2:
                    return f"{month1} {day1:2d}, {year1}"
                return     f"{time1} - {time2} on {month1} {day1:2d}, {year1}"
            else:
                return     f"{month1} {day1:2d} - {day2:2d}, {year1}"
        else:
            return         f"{month1} {day1:2d} - {month2} {day2:2d}, {year1}"
    else:
        return             f"{month1} {day1:2d}, {year1} - {month2} {day2:2d}, {year2}"

_TIMESTAMP_PATTERN_RE: re.Pattern = re.compile(r"(\d{8}-\d{6})\.pkl$")

def extract_timestamp(the_string: str) -> str | None:
    """Extract the timestamp (YYYYMMDD-HHMMSS) from a name ending in "YYYYMMDD-HHMMSS.pkl", or None if it doesn't."""
    if (m := _TIMESTAMP_PATTERN_RE.search(the_string)):
        return m.group(1)
    return None

_TZ_ABBREV_TO_ZONE: dict[str, str] = {
    "EST"  : "America/New_York",
    "EDT"  : "America/New_York",
    "CST"  : "America/Chicago",  # WARNING! "CST" can also mean China Standard Time (Asia/Shanghai, UTC+8), so use with caution!
    "CDT"  : "America/Chicago",
    "MST"  : "America/Denver",
    "MDT"  : "America/Denver",
    "PST"  : "America/Los_Angeles",
    "PDT"  : "America/Los_Angeles",
    "HST"  : "Pacific/Honolulu",
    "AKST" : "America/Anchorage",
    "AKDT" : "America/Anchorage",
    "AST"  : "America/Puerto_Rico",  # Atlantic Standard Time
    "ADT"  : "America/Puerto_Rico",  # Atlantic Daylight Time
    "NST"  : "America/St_Johns",     # Newfoundland Standard Time
    "NDT"  : "America/St_Johns",     # Newfoundland Daylight Time
    "BST"  : "Europe/London",        # British Summer Time
    "CET"  : "Europe/Berlin",        # Central European Time
    "CEST" : "Europe/Berlin",        # Central European Summer Time
    "EET"  : "Europe/Athens",        # Eastern European Time
    "EEST" : "Europe/Athens",        # Eastern European Summer Time
    "IST"  : "Asia/Kolkata",         # Indian Standard Time - WARNING! "IST" can also mean Irish Standard Time (Europe/Dublin, UTC+1), so use with caution!
    "JST"  : "Asia/Tokyo",           # Japan Standard Time
    "KST"  : "Asia/Seoul",           # Korea Standard Time
    "HKT"  : "Asia/Hong_Kong",       # Hong Kong Time
    "SGT"  : "Asia/Singapore",       # Singapore Time
    "AEST" : "Australia/Sydney",     # Australian Eastern Standard Time
    "AEDT" : "Australia/Sydney",     # Australian Eastern Daylight Time
    "ACST" : "Australia/Adelaide",   # Australian Central Standard Time
    "ACDT" : "Australia/Adelaide",   # Australian Central Daylight Time
    "AWST" : "Australia/Perth",      # Australian Western Standard Time
    "AWDT" : "Australia/Perth",      # Australian Western Daylight Time
    "NZT"  : "Pacific/Auckland",     # New Zealand Time
    "NZST" : "Pacific/Auckland",     # New Zealand Standard Time
    "NZDT" : "Pacific/Auckland",     # New Zealand Daylight Time
    "WET"  : "Europe/Lisbon",        # Western European Time
    "WEST" : "Europe/Lisbon",        # Western European Summer Time
    # ...add any others you need
}

_TZ_OFFSET_RE: re.Pattern = re.compile(r'''
    ^(?P<sign>[+-])
    (?:
        (?P<hours1>\d{1,2})[hH](?P<mins1>\d{1,2})(?:[mM])?  # +5h30m
      | (?P<hours1_only>\d{1,2})[hH]                        # +5h
      | (?P<hours2>\d{1,2}):(?P<mins2>\d{2})                # +5:30
      | (?P<hours3>\d{1,2})(?P<mins3>\d{2})                 # +0530
      | (?P<hours4>\d{1,2})                                 # +5
    )
    $
''', re.VERBOSE)

def parse_timezone(tz_arg: str | dt.tzinfo | None = None) -> dt.tzinfo | str:
    """
    Parse the given timezone string or tzinfo object into a datetime.tzinfo object.
    If tz_arg is None, return UTC timezone.
    If tz_arg is a string, it can be in one of the following formats:
      - A fixed‐offset like: "+HH:MM", "+HHMM", "+H", "+Hh", "+HhMMm" (or minus variants).
         Examples: "+05:30", "-0530", "+5h", "-5h30m".
      - A string that can be converted to a ZoneInfo object (e.g. 'America/New_York').
      - A timezone abbreviation that maps to a known IANA zone name (e.g. 'EST', 'CET').
      - "Z", "UTC", or "GMT" (case‐insensitive) to represent UTC.
      - A string "Naive" to represent a naive datetime (no timezone).
    If tz_arg is already a tzinfo object, return it as is.

    Args:
        tz_arg : A timezone string, a datetime.tzinfo object, or None.

    Returns:
        A datetime.tzinfo object representing the parsed timezone, or a string "Naive"
        if the input was "Naive".

    Raises:
        ValueError if the string cannot be converted to a valid timezone.
    """

    import datetime as dt

    # If tz_arg is None, return UTC timezone
    if tz_arg is None:
        return dt.timezone.utc

    # If tz_arg is already a tzinfo object, return it unchanged
    if isinstance(tz_arg, dt.tzinfo):
        return tz_arg

    # If tz_arg is a string, try to parse it
    if isinstance(tz_arg, str):
        s = tz_arg.strip()
        up = s.upper()

        # Handle "Naive" case
        if up == "NAIVE":
            return tz_arg

        # Bare UTC/GMT/Z
        if up in ("Z", "UTC", "GMT"):
            return dt.timezone.utc

        # Strip leading "UTC" or "GMT" prefix
        if up.startswith(("UTC", "GMT")):
            s = s[3:].strip()  # now s begins with + or -

        # Try fixed-offset patterns
        m = _TZ_OFFSET_RE.fullmatch(s)
        if m:
            sign = 1 if m.group("sign") == "+" else -1

            if m.group("hours1") is not None:
                hours   = int(m.group("hours1"))
                minutes = int(m.group("mins1"))
            elif m.group("hours1_only") is not None:
                hours   = int(m.group("hours1_only"))
                minutes = 0
            elif m.group("hours2") is not None:
                hours   = int(m.group("hours2"))
                minutes = int(m.group("mins2"))
            elif m.group("hours3") is not None:
                hours   = int(m.group("hours3"))
                minutes = int(m.group("mins3"))
            else:
                hours   = int(m.group("hours4"))
                minutes = 0

            offset = dt.timedelta(hours=hours, minutes=minutes) * sign
            return dt.timezone(offset)

        # Otherwise, fall back to ZoneInfo
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        # Try to interpret the string as a timezone abbreviation
        if up in _TZ_ABBREV_TO_ZONE:
            zone_name = _TZ_ABBREV_TO_ZONE[up]
            return ZoneInfo(zone_name)

        # Try to interpret the string as a ZoneInfo name
        try:
            return ZoneInfo(tz_arg.strip())
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"Unknown timezone {tz_arg!r}: {e}") from e

    raise TypeError(f"Expected None, str, or tzinfo; got {type(tz_arg).__name__!r}")

def decimal_year_to_datetime(dec: float, use_astropy: bool = False) -> dt.datetime:
    """
    Convert a decimal year to a datetime object.
    If use_astropy is True, astropy.time is used for sub-second and leap-second–aware conversion.
    Usage: new_datetime_datetime_object = decimal_year_to_datetime(2002.291)
    """
    import datetime as dt
    if use_astropy:
        try:
            from astropy.time import Time
        except ImportError as e:
            raise ValueError(f"'use_astropy=True' requires the astropy package: {e}") from e
        t = Time(dec, format="jyear", scale="utc")
        return t.to_datetime().replace(tzinfo=dt.timezone.utc)

    import calendar
    try:
        year = int(dec)
        rem = dec - year
        start_dt = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        # From the calendar, not from 1 January of year + 1, which doesn't exist for 9999.
        year_secs = (366 if calendar.isleap(year) else 365) * 86_400
        return start_dt + dt.timedelta(seconds=rem * year_secs)
    except (ValueError, OverflowError) as e:  # OverflowError: inf, or a year too big for C
        raise ValueError(f"Failed to convert decimal year {dec} to datetime: {e}") from e

def _parse_iso(given_date: str) -> dt.datetime:
    """Parse an ISO8601 date string and return a datetime object. Raises ValueError if the date string is invalid."""
    from dateutil.parser import isoparse
    return isoparse(given_date)

_JD_MJD_CAPTURE_RE: re.Pattern = re.compile(r"\s*(?P<prefix>JD|MJD)?\s*(?P<value>[+-]?\d+(?:\.\d+)?)\s*", re.IGNORECASE)

_JD_UNIX_EPOCH: float = 2_440_587.5

AnyDateTimeType: TypeAlias = "str | float | int | np.datetime64 | pd.Timestamp | dt.datetime"

def _finalize_datetime(parsed_dt: dt.datetime, tz_arg: str | dt.tzinfo | None,
                       should_convert: bool | None = None) -> dt.datetime:
    """
    Put the parsed datetime into the target timezone.

    A datetime that carries its own zone or offset is converted, so the clock
    shifts to show the same instant; a naive one has the target zone attached,
    so the clock stays. 'should_convert' overrides that choice, and a naive
    datetime that must be converted is read as UTC, the default zone.

    Args:
        parsed_dt:      The datetime parsed from the caller's input.
        tz_arg:         The target timezone: a string, a datetime.tzinfo object, or None for UTC.
        should_convert: True to convert, False to attach, None to decide by whether parsed_dt is aware.

    Returns:
        A datetime.datetime object in the target timezone, or a naive one if tz_arg is "Naive".

    Raises:
        ValueError: If the tz_arg is not a valid timezone string or tzinfo object.
    """
    import datetime as dt
    if isinstance(tz_arg, str) and tz_arg.strip().upper() == "NAIVE":
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Naive timezone requested, returning datetime %s without any timezone info", parsed_dt)
        return parsed_dt.replace(tzinfo=None)
    target_tz = parse_timezone(tz_arg)
    is_aware  = parsed_dt.utcoffset() is not None
    if should_convert if should_convert is not None else is_aware:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Converting datetime %s to timezone %s by shifting the clock", parsed_dt, target_tz)
        if not is_aware:
            # Read a bare wall time as UTC, not as the host's local time.
            parsed_dt = parsed_dt.replace(tzinfo=dt.timezone.utc)
        return parsed_dt.astimezone(target_tz)
    else:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Attaching timezone %s to datetime %s without shifting the clock", target_tz, parsed_dt)
        return parsed_dt.replace(tzinfo=target_tz)

def parse_datetime(given_date: AnyDateTimeType, timezone: str | dt.tzinfo | None = None,
                   format_str: str | None = None,
                   should_convert: bool | None = None) -> dt.datetime:
    """
    Try parsing the given_date string or number into a datetime.datetime object in the specified timezone.

    If "format_str" is provided, it will be used to parse the date string. These format types are accepted:
     - "seconds" or "milliseconds" indicating the number of seconds or milliseconds since an epoch (Unix epoch by default).
     - "YYYY-MM-DD" or similar ISO8601 formats such as "YYYY-MM-DDTHH:MM:SS", "MM/DD/YYYY", etc.
     - A custom string following this pattern: "units (optional: since/after epoch)", where "units" can be anything that the function seconds_in_unit() accepts (e.g. "days", "weeks", "months", etc.). The optional epoch time can be a string, float, int, numpy.datetime64, pandas.Timestamp, or datetime.datetime object. Example: "days since 1990", "milliseconds after J2000", "sidereal days since 2000-01-01", etc. If the epoch is not specified, it defaults to the Unix epoch (1970-01-01T00:00:00Z)

    If a boolean "should_convert" is provided, it will override the default behavior of whether to convert the datetime to the specified timezone by shifting the clock or just attaching the timezone without shifting. If None, a date that carries its own timezone or offset (an aware datetime, "...Z", "...+02:00", "... EST") is converted, and one without is given the target timezone; a naive date that must be converted is read as UTC.

    If a given_date starts with "JD" or "MJD", it will be treated as a Julian Date or Modified Julian Date, respectively.

    Otherwise, if given_date is a float or int, treat it as a decimal year by default if format_str is not provided.

    Any call that doesn't provide a timezone argument will default to UTC.
    The timezone can be a datetime.tzinfo object or a string that can be converted to a ZoneInfo object (e.g. 'America/New_York').
    If the given_date is an "aware" datetime.datetime object which already has a timezone attached, it will be converted to the specified timezone (which may involve changing its date and time if the specified timezone is different).
    The timezone can also be a fixed‐offset like "+05:30" or "-04:00", or the string "Naive" to indicate that the datetime should be treated as a naive datetime (i.e. without any timezone information).

    Accepts:
        'NOW' (case-insensitive) → current datetime
        strings in YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, or other ISO8601 formats (e.g. '2002-10-18T07:00:00Z', '2002-10-18 07:00:00+00:00').
        If YYYY is provided, it will default to January 1st of that year at midnight in the target timezone.
        If YYYY-MM is provided, it will default to the first day of that month at midnight.
        If YYYY-MM-DD is provided, it will default to midnight on that day.
        fallback to dateutil.parser.parse for free-form strings ("18 Oct 2002", "March 5th, 2020", etc.)
        floats (e.g. 2002.29178082191777) or integer (e.g. 2002) → decimal year, read in the target timezone
        numpy.datetime64 objects (e.g. np.datetime64('2002-10-18T07:00:00'))
        pandas.Timestamp objects (e.g. pd.Timestamp('2002-10-18 07:00:00'))
        datetime.datetime objects (e.g. datetime.datetime(2002, 10, 18, 7, 0, 0))

    Args:
        given_date:     The date to parse, which can be a string, float, int, numpy.datetime64,
                        pandas.Timestamp, or datetime.datetime object.
        timezone:       A string or datetime.tzinfo object representing the timezone to convert
                        the datetime to. If None, defaults to UTC.
        format_str:     A string indicating the format of the date. If None, the function will
                        try to infer the format from the given_date.
        should_convert: A boolean indicating whether to convert the datetime to the specified
                        timezone by shifting the clock (True) or just attaching the timezone
                        without shifting (False). If None, dates that carry a timezone or
                        offset are converted and dates without one are attached.

    Returns:
        datetime.datetime object in the specified timezone.
        Note that datetime.datetime objects cannot represent dates before 1 January 0001 or after 31 December 9999.
        So dates outside this range will raise a ValueError.

    Raises:
        ValueError:  If the given_date cannot be parsed into a datetime object, or if the timezone is invalid.
        TypeError:   If the given_date is not a string, float, int, numpy.datetime64, pandas.Timestamp, or datetime.datetime object.
    """
    import datetime as dt
    fallback_logging_config()  # Ensure logging is configured

    parsed_tz = parse_timezone(timezone)  # Ensure timezone is a valid tzinfo object or string

    parsed_dt = None

    # Handle special cases:
    if isinstance(given_date, str):
        if given_date.strip().upper() == "J2000":
            # J2000 is January 1, 2000, 11:58:55.816 UTC
            parsed_dt = dt.datetime(2000, 1, 1, 11, 58, 55, 816_000, tzinfo=dt.timezone.utc)
        if given_date.strip().upper() == "UNIX":
            # UNIX epoch is January 1, 1970, 00:00:00 UTC
            parsed_dt = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        if given_date.strip().upper() == "NOW":
            parsed_dt = dt.datetime.now(tz=dt.timezone.utc)

    # Handle forced or explicit Julian Date (JD) or Modified Julian Date (MJD)
    m: re.Match | None = None
    prefix: str | None = None
    if parsed_dt is None and isinstance(given_date, str):
        m = _JD_MJD_CAPTURE_RE.fullmatch(given_date)
        if m:
            prefix = m.group("prefix")

    # Trigger JD/MJD branch only if format_str equals "JD" or "MJD", or prefix was provided
    if parsed_dt is None and (prefix is not None or (format_str and (format_str.upper() == "JD" or format_str.upper() == "MJD"))):
        # Determine raw value
        if isinstance(given_date, (int, float)):
            value = float(given_date)
        else:
            if m is not None:
                value = float(m.group("value"))
            else:
                try:
                    value = float(given_date.strip())
                except ValueError as e:
                    raise ValueError(f"Expected a JD/MJD numeric value, got {given_date!r}") from e

        # Determine if MJD conversion needed
        use_mjd = bool((format_str and format_str.upper() == "MJD") or (prefix and prefix.upper() == "MJD"))

        # Convert MJD to JD if necessary, then to datetime via timedelta from Unix epoch
        jd_val    = value + (2_400_000.5 if use_mjd else 0.0)
        unix_secs = (jd_val - _JD_UNIX_EPOCH) * 86_400
        parsed_dt = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=unix_secs)

    # Check if the given_date is a string that can be parsed as a float
    if parsed_dt is None and isinstance(given_date, str) and is_float(given_date):
        given_date = float(given_date)  # Convert string to float if it represents a number
    # Check if the given_date is a float or int but NOT a boolean
    if parsed_dt is None and isinstance(given_date, (int, float)) and not isinstance(given_date, bool):
        if format_str is None:
            # A decimal year is read in the target timezone: 2002 is midnight on
            # 1 January there. Dropping the UTC zone makes the finalizer attach it.
            parsed_dt = decimal_year_to_datetime(float(given_date)).replace(tzinfo=None)
        else:  # If format is provided, parse the date using the specified format.
            if not isinstance(format_str, str):
                raise TypeError(f"Expected 'format' to be a string, got {type(format_str).__name__!r}")
            # Make sure the format string is a valid example of "units (optionally: since/after epoch)"
            # Try to split by since or after, whichever works:
            format_parts = re.split(r'\s+(since|after)\s+', format_str, maxsplit=1)
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Parsing date with format string: '%s' split into parts: %s", format_str, format_parts)
            # The first part should be acceptable by seconds_in_unit():
            try:
                units      = format_parts[0].strip()
                multiplier = seconds_in_unit(units)  # This will raise ValueError if the unit is unknown
            except ValueError as e:
                raise ValueError(f"Invalid time unit '{units}' in format string '{format_str}': {e}") from e
            # If the format_parts list has only one part, it means the epoch defaults to the Unix epoch (1970-01-01T00:00:00Z).
            if len(format_parts) == 1:
                # If the format_parts list has only one part, it means the format is just "units" (e.g. "days", "weeks", etc.)
                # In this case, we assume the epoch is the Unix epoch (1970-01-01T00:00:00Z).
                epoch_str = "1970-01-01T00:00:00Z"
            else:
                # If the format_parts list has three parts, the third part is the epoch.
                epoch_str = format_parts[2].strip()
            try:
                epoch = parse_datetime(epoch_str, timezone=parsed_tz)
            except ValueError as e:
                raise ValueError(f"Invalid epoch '{epoch_str}' in format string '{format_str}': {e}") from e
            # Now we can calculate the datetime based on the given_date (and the multiplier from 'units') and the epoch
            parsed_dt = epoch + dt.timedelta(seconds=float(given_date) * multiplier)

    if parsed_dt is None and type(given_date) is dt.datetime:  # Don't use isinstance() here, because it will also match subclasses like Pandas Timestamp
        parsed_dt = given_date
    # Handle date objects (without time) as midnight. Exclude datetimes: pandas'
    # Timestamp subclasses datetime (and so date) and is handled below.
    elif isinstance(given_date, dt.date) and not isinstance(given_date, dt.datetime):
        parsed_dt = dt.datetime.combine(given_date, dt.time.min)

    if parsed_dt is None:
        try:
            import numpy as np
        except ImportError:
            np = None
        if np is not None and isinstance(given_date, np.datetime64):
            ts_ns     = given_date.astype("datetime64[ns]").astype("int64")
            parsed_dt = dt.datetime.fromtimestamp(
                ts_ns / 1e9,
                # UTC, never None, which would give the host's local time; the
                # finalizer converts to the target zone or, for "Naive", drops it.
                tz=dt.timezone.utc,
            )

    if parsed_dt is None:
        try:
            import pandas as pd
        except ImportError:
            pd = None
        if pd is not None and isinstance(given_date, pd.Timestamp):
            parsed_dt = given_date.to_pydatetime()

    error_message: str = f"The date '{given_date}' is type {type(given_date).__name__!r} in an unknown format. Please use NOW, YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, other ISO8601 strings, or a decimal year like 2002.291. Datetimes in pandas.Timestamp, numpy.datetime64, or datetime.datetime formats are also accepted and will be converted to datetime.datetime objects in the specified timezone ({parsed_tz})."

    if parsed_dt is None and not isinstance(given_date, str):
        raise TypeError(error_message)

    if parsed_dt is not None:
        # Finalize the datetime object by converting it to the target timezone or just attaching the timezone without shifting the clock
        return _finalize_datetime(parsed_dt, parsed_tz, should_convert)

    # From here on, we know it's a str (we raised or otherwise handled non-str types above)
    assert isinstance(given_date, str)
    given_string = given_date

    if parsed_dt is None and format_str is not None:
        try:
            parsed_dt = dt.datetime.strptime(given_string, format_str)
        except ValueError as e:
            raise ValueError(f"Invalid date format '{given_string}' with specified format '{format_str}': {e}") from e

    # Try parsing the date string in various formats
    # Start with RFC 2822 format, then ISO8601, then free-form strings
    # Store any errors encountered in a list to provide feedback if all parsing attempts fail.
    errors: list[str] = []

    if parsed_dt is None:
        import email.utils
        try:
            # parses "Tue, 25 Jun 2025 14:00:00 GMT"
            parsed_dt = email.utils.parsedate_to_datetime(given_string)
        except (TypeError, ValueError) as e:
            errors.append(f"Failed to parse '{given_string}' as an RFC 2822 date: {e}")

    if parsed_dt is None:
        try:
            parsed_dt = _parse_iso(given_string)
        except ValueError as e:
            errors.append(f"Failed to parse '{given_string}' as an ISO8601 date: {e}")

    if parsed_dt is None:
        try:
            from dateutil.parser import parse as parse_fuzzy
            parsed_dt = parse_fuzzy(given_string, default=dt.datetime(1900, 1, 1))
        except ValueError as e:
            errors.append(f"Failed to parse '{given_string}' as a free-form date string: {e}")

    if parsed_dt is None:
        if np is None:
            errors.append("The numpy package is not installed, so numpy.datetime64 objects cannot be parsed.")
        if pd is None:
            errors.append("The pandas package is not installed, so pandas.Timestamp objects cannot be parsed.")
    else:
        # Finalize the datetime object by converting it to the target timezone or just attaching the timezone without shifting the clock
        return _finalize_datetime(parsed_dt, parsed_tz, should_convert)

    raise ValueError(error_message + "\n".join(map(str, errors)) + "\nPlease check the input format and try again.")

class Precision:
    """Integer constants representing date-formatting precision levels.

    Levels are ordered from coarsest (YEAR=0) to finest (SECOND=4).
    """

    YEAR:   Final[int] = 0
    MONTH:  Final[int] = 1
    DAY:    Final[int] = 2
    MINUTE: Final[int] = 3
    SECOND: Final[int] = 4

ADAPTIVE_FORMAT_LEVELS: Final[list[str]] = [
    "%Y",                 # 0: year     (2024)
    "%Y-%m",              # 1: month    (2024-03)
    "%Y-%m-%d",           # 2: day      (2024-03-15)
    "%Y-%m-%d %H:%M",     # 3: minute   (2024-03-15 09:30)
    "%Y-%m-%d %H:%M:%S",  # 4: second   (2024-03-15 09:30:45)
]

def _normalize_to_datetime(date: AnyDateTimeType) -> "dt.datetime | None":
    """Convert a single date value to datetime.datetime.

    Accepts datetime.datetime, numpy.datetime64, and matplotlib date floats.
    Returns None for NaT/NaN values.

    Args:
        date: A date value in any supported format.

    Returns:
        A datetime.datetime object, or None if the value is NaT/NaN.
    """
    import datetime as dt
    import numpy as np

    if isinstance(date, dt.datetime):
        return date
    if isinstance(date, (int, float)):
        if np.isnan(date):
            return None
        import matplotlib.dates as mdates
        return mdates.num2date(date).replace(tzinfo=None)
    if isinstance(date, np.datetime64):
        if np.isnat(date):
            return None
        ts = (date - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
        return dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc).replace(tzinfo=None)
    msg = f"Unsupported date type: {type(date)}"
    raise TypeError(msg)

def adaptive_date_labels(
    dates: "Sequence[AnyDateTimeType]",
    *,
    min_precision: int = Precision.YEAR,
    max_precision: int = Precision.SECOND,
    format_levels: "list[str] | None" = None,
) -> list[str]:
    """Format dates at the coarsest precision that produces unique labels.

    Given a sequence of dates, starts formatting at the coarsest level and
    refines until all labels are unique or max_precision is reached.

    Args:
        dates: Sequence of date values (datetime.datetime, numpy.datetime64,
            or matplotlib date floats).
        min_precision: Minimum precision level (default: Precision.YEAR).
            The formatter will never produce labels coarser than this.
        max_precision: Maximum precision level (default: Precision.SECOND).
            The formatter stops refining at this level even if labels collide.
        format_levels: Custom format strings for each level. Must have length
            >= max_precision + 1. Defaults to ADAPTIVE_FORMAT_LEVELS.

    Returns:
        List of formatted date strings, one per input date. Empty strings
        for NaT/NaN values.
    """
    import numpy as np

    if isinstance(dates, np.ndarray):
        if dates.size == 0:
            return []
    elif not dates:
        return []

    levels = format_levels if format_levels is not None else ADAPTIVE_FORMAT_LEVELS

    normalized = [_normalize_to_datetime(d) for d in dates]

    if len(normalized) == 1:
        d = normalized[0]
        level = max(min_precision, Precision.DAY)
        level = min(level, max_precision)
        if d is None:
            return [""]
        return [d.strftime(levels[level])]

    for level in range(min_precision, max_precision + 1):
        fmt = levels[level]
        labels = [d.strftime(fmt) if d is not None else "" for d in normalized]
        non_empty = [lbl for lbl in labels if lbl != ""]
        if len(set(non_empty)) == len(non_empty):
            return labels

    fmt = levels[max_precision]
    return [d.strftime(fmt) if d is not None else "" for d in normalized]

@functools.cache
def _formatter_class(cls: type[AdaptiveDateFormatter]) -> type[AdaptiveDateFormatter]:
    """Return a subclass of both `cls` and `matplotlib.ticker.Formatter`.

    Built on first use and cached per class, so matplotlib is imported when a
    formatter is first constructed rather than when this module is imported.

    Args:
        cls: `AdaptiveDateFormatter` or a subclass of it.

    Returns:
        A class named like `cls` whose instances matplotlib accepts as a
        `Formatter` as-is, instead of wrapping them in a `FuncFormatter`.
        It records `cls` as its ``_public_class``, the class to pickle by.
        `cls` itself if it already is a `Formatter`, as ``type(fmt)`` is.

    Raises:
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib.ticker as mticker
    except ImportError as exc:
        msg = ("AdaptiveDateFormatter needs matplotlib, an optional dependency: "
               "pip install 'emmykit[datetime]'")
        raise ImportError(msg) from exc

    if issubclass(cls, mticker.Formatter):
        return cls
    namespace = {"__module__": cls.__module__, "__qualname__": cls.__qualname__,
                 "_public_class": cls}
    return type(cls.__name__, (cls, mticker.Formatter), namespace)

def _new_without_init(cls: type[AdaptiveDateFormatter]) -> AdaptiveDateFormatter:
    """Create an uninitialized instance of `cls` that is also a `Formatter`.

    Unpickling and copying call this and then restore the instance's state,
    as Python's default pickling does, so ``__init__`` does not run again.

    Args:
        cls: The public class: `AdaptiveDateFormatter` or a subclass of it.

    Returns:
        An instance of `_formatter_class(cls)`, without its state.
    """
    formatter_class = _formatter_class(cls)
    return formatter_class.__new__(formatter_class)

# Type checkers are told the base every instance really has (see
# `_formatter_class`); at run time it stays `object`, so importing this
# module still does not import matplotlib.
if TYPE_CHECKING:
    from matplotlib.ticker import Formatter as _FormatterBase
else:
    _FormatterBase = object

class AdaptiveDateFormatter(_FormatterBase):
    """Matplotlib Formatter that auto-selects date label precision.

    Uses adaptive disambiguation: labels start at the coarsest level and
    refine until all tick labels are unique. Drop-in replacement for any
    matplotlib axis formatter or colorbar formatter.

    Every instance is a real `matplotlib.ticker.Formatter`, so matplotlib
    installs it as-is and hands `format_ticks` all the ticks at once, which
    is what lets it compare them. matplotlib is imported on first
    construction rather than with this module, so ``import emmykit`` stays
    stdlib-only. An instance's class is a subclass built at that point;
    ``isinstance(fmt, AdaptiveDateFormatter)`` holds as usual. Type checkers
    see `Formatter` as the declared base, so passing an instance to
    ``set_major_formatter`` type-checks without a cast.

    A subclass's ``__init__`` must call ``super().__init__()``, which is
    where the class is swapped. The built class is itself a subclass, so
    ``__init_subclass__`` hooks see it too; a subclass that lists
    `Formatter` among its bases, ``class S(AdaptiveDateFormatter,
    Formatter)``, is used as it is and gets no built class.

    Args:
        min_precision: Minimum precision level (default: Precision.YEAR).
        max_precision: Maximum precision level (default: Precision.SECOND).
        format_levels: Custom format strings per level.

    Raises:
        ImportError: On construction, if matplotlib is not installed
            (``pip install 'emmykit[datetime]'``).

    Example:
        >>> ax.xaxis.set_major_formatter(AdaptiveDateFormatter())
        >>> cbar.ax.yaxis.set_major_formatter(AdaptiveDateFormatter())
    """

    def __init__(
        self,
        *,
        min_precision: int = Precision.YEAR,
        max_precision: int = Precision.SECOND,
        format_levels: "list[str] | None" = None,
    ) -> None:
        """Initialize the AdaptiveDateFormatter.

        Args:
            min_precision: Minimum precision level.
            max_precision: Maximum precision level.
            format_levels: Custom format strings per level.

        Raises:
            ImportError: If matplotlib is not installed.
        """
        # Swapped here rather than in __new__, so construction stays plain
        # Python: whatever a subclass's __init__ takes reaches it untouched.
        self.__class__ = _formatter_class(type(self))
        self._min_precision = min_precision
        self._max_precision = max_precision
        self._format_levels = format_levels
        self._cached_labels: dict[float, str] = {}

    def __reduce__(self) -> tuple[Any, ...]:
        """Pickle by the public class rather than the run-time one.

        A class built by `_formatter_class` cannot be found by name, so
        pickling its instances as-is would fail, and with it any matplotlib
        figure the formatter is installed on. Instances of a class that
        already was a `Formatter` keep that class and pickle by it.

        As with default pickling, the state is whatever ``__getstate__``
        returns (``__dict__`` plus any slot values, unless a subclass
        overrides it), and unpickling restores it without calling
        ``__init__``, so a subclass may give ``__init__`` required arguments.

        Returns:
            `_new_without_init`, its argument (the public class), and the
            instance state to restore afterwards.
        """
        # vars(), not getattr(): a subclass of a built class inherits the
        # attribute, but it is a public class in its own right.
        public_class = vars(type(self)).get("_public_class", type(self))
        return (_new_without_init, (public_class,), self.__getstate__())

    def format_ticks(self, values: list[float]) -> list[str]:
        """Format all tick values collectively with disambiguation.

        Args:
            values: List of matplotlib date floats (from date2num).

        Returns:
            List of formatted label strings.
        """
        labels = adaptive_date_labels(
            values,
            min_precision=self._min_precision,
            max_precision=self._max_precision,
            format_levels=self._format_levels,
        )
        self._cached_labels = dict(zip(values, labels))
        return labels

    def __call__(self, x: float, pos: "int | None" = None) -> str:
        """Format a single tick value.

        Uses cached results from format_ticks if available, otherwise
        formats independently at the day level.

        Args:
            x: A matplotlib date float.
            pos: Tick position (unused, required by matplotlib protocol).

        Returns:
            Formatted date string.
        """
        if x in self._cached_labels:
            return self._cached_labels[x]
        labels = adaptive_date_labels(
            [x],
            min_precision=self._min_precision,
            max_precision=self._max_precision,
            format_levels=self._format_levels,
        )
        return labels[0] if labels else ""
