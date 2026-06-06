"""numeric_helpers — extracted from univ_defs.py."""

from __future__ import annotations

_UNIT_SECONDS = {
    **dict.fromkeys(["year", "years", "yr", "yrs", "calendar year", "calendar years"],    31_556_952),  # Average calender year = 365.2425 days (accounting for leap years)
    **dict.fromkeys(["solar year", "solar years", "tropical year", "tropical years"],     31_556_925.216),  # Average solar/tropical year = 365.24219 solar days = time for Earth to orbit the Sun once relative to the Sun/equinoxes
    **dict.fromkeys(["sidereal year", "sidereal years"],                                  31_558_149.54),  # Sidereal year = 365.25636 days = time for Earth to orbit the Sun once relative to the "fixed" stars
    **dict.fromkeys(["month", "months", "mo", "mos", "calendar month", "calendar months"], 2_629_746.0),  # Average calendar month = 30.436875 solar days
    **dict.fromkeys(["lunar month", "lunar months", "synodic month", "synodic months"],    2_551_442.9),  # Average lunar month (synodic month) = 29.53 solar days
    **dict.fromkeys(["week", "weeks", "wk", "wks"],                                          604_800.0),  # 7 solar days
    **dict.fromkeys(["day", "days", "d", "solar day", "solar days", "ephemeris day", "ephemeris days"], 86_400),  # 24 hours = time for Earth to rotate once relative to the Sun
    **dict.fromkeys(["sidereal day", "sidereal days"],                                                  86_164.0905),  # 23 hours, 56 minutes, 4.1 seconds = time for Earth to rotate once relative to the "fixed" stars
    **dict.fromkeys(["hour",         "hours",   "hr",  "hrs"],          3600),
    **dict.fromkeys(["minute",       "minutes", "min", "mins"],           60),
    **dict.fromkeys(["second",       "seconds", "sec", "secs", "s"],    1.00),
    **dict.fromkeys(["decisecond",   "deciseconds",  "ds"],            1E-01),
    **dict.fromkeys(["centisecond",  "centiseconds", "cs"],            1E-02),
    **dict.fromkeys(["millisecond",  "milliseconds", "ms"],            1E-03),
    **dict.fromkeys(["microsecond",  "microseconds", "us", "μs"],      1E-06),
    **dict.fromkeys(["nanosecond",   "nanoseconds",  "ns"],            1E-09),
    **dict.fromkeys(["picosecond",   "picoseconds",  "ps"],            1E-12),
    **dict.fromkeys(["femtosecond",  "femtoseconds", "fs"],            1E-15),
    **dict.fromkeys(["attosecond",   "attoseconds",  "as"],            1E-18),
    **dict.fromkeys(["zeptosecond",  "zeptoseconds", "zs"],            1E-21),
    **dict.fromkeys(["yoctosecond",  "yoctoseconds", "ys"],            1E-24),
    **dict.fromkeys(["planck time",  "planck times", "planck", "plancks", "pt"], 5.391_247E-44),  # Planck time
    **dict.fromkeys(["decade",       "decades"],                                315_569_252.16),  #   10 solar years
    **dict.fromkeys(["century",      "centuries"],                            3_155_692_521.60),  #  100 solar years
    **dict.fromkeys(["millennium",   "millennia"],                           31_556_925_216.00),  # 1000 solar years
    **dict.fromkeys(["megayear",     "megayears", "mya", "myr"],         31_556_925_216_000.00),  # 1E06 solar years
    **dict.fromkeys(["gigayear",     "gigayears", "gya", "gyr"],     31_556_925_216_000_000.00),  # 1E09 solar years
    **dict.fromkeys(["terayear",     "terayears", "tya", "tyr"], 31_556_925_216_000_000_000.00),  # 1E12 solar years
    **dict.fromkeys(["fortnight",    "fortnights"],                               1_209_600.00),  # 2 weeks = 604_800 * 2 seconds
    **dict.fromkeys(["decasecond",   "decaseconds",   "das"], 1E01),
    **dict.fromkeys(["hectosecond",  "hectoseconds",  "hs"],  1E02),
    **dict.fromkeys(["kilosecond",   "kiloseconds",   "ks"],  1E03),
    **dict.fromkeys(["megasecond",   "megaseconds"],          1E06),  # no Ms because .casefold() would convert it to ms
    **dict.fromkeys(["gigasecond",   "gigaseconds",   "gs"],  1E09),
    **dict.fromkeys(["terasecond",   "teraseconds",   "ts"],  1E12),
    **dict.fromkeys(["petasecond",   "petaseconds"],          1E15),  # no Ps because .casefold() would convert it to ps
    **dict.fromkeys(["exasecond",    "exaseconds",    "es"],  1E18),
    **dict.fromkeys(["zettasecond",  "zettaseconds"],         1E21),  # no Zs because .casefold() would convert it to zs
    **dict.fromkeys(["yottasecond",  "yottaseconds"],         1E24),  # no Ys because .casefold() would convert it to ys
    **dict.fromkeys(["ronnasecond",  "ronnaseconds",  "rs"],  1E27),
    **dict.fromkeys(["quettasecond", "quettaseconds", "qs"],  1E30),
}

def seconds_in_unit(unit: str) -> float:
    """Return the number of seconds in a given time unit."""
    try:
        return _UNIT_SECONDS[unit.casefold()]
    except KeyError:
        raise ValueError(f"Unknown time unit: {unit!r}")

def is_float(s: str) -> bool:
    """Check if a string can be parsed as a float."""
    try:
        float(s)
        return True
    except ValueError:
        return False
