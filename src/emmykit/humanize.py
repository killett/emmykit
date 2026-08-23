"""humanize — extracted from univ_defs.py."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    """A unit of measurement, in the three spellings a formatter needs.

    Long names cannot be derived from the symbol ("m" -> "meter"/"meters",
    "Hz" -> "hertz"/"hertz"), so all three are carried explicitly.

    Attributes:
        symbol:   Short symbol, appended after the prefix symbol ("m", "B", "Hz").
        singular: Long name used when the formatted number reads exactly "1".
        plural:   Long name used otherwise; equal to `singular` for units such as
                  hertz that have no plural "s".
    """

    symbol: str
    singular: str
    plural: str


BYTES = Unit("B", "byte", "bytes")
METERS = Unit("m", "meter", "meters")
GRAMS = Unit("g", "gram", "grams")
SECONDS = Unit("s", "second", "seconds")
JOULES = Unit("J", "joule", "joules")
WATTS = Unit("W", "watt", "watts")
HERTZ = Unit("Hz", "hertz", "hertz")

# Prefix tables, written as (power, symbol, long name). Decimal powers are
# powers of ten; binary powers are powers of two. Ordered largest first so the
# selector can take the first entry that fits.
_SI_MULTIPLES: tuple[tuple[int, str, str], ...] = (
    (30, "Q", "quetta"), (27, "R", "ronna"), (24, "Y", "yotta"),
    (21, "Z", "zetta"), (18, "E", "exa"), (15, "P", "peta"),
    (12, "T", "tera"), (9, "G", "giga"), (6, "M", "mega"), (3, "k", "kilo"),
)
_SI_SUBMULTIPLES: tuple[tuple[int, str, str], ...] = (
    (-3, "m", "milli"), (-6, "µ", "micro"), (-9, "n", "nano"),
    (-12, "p", "pico"), (-15, "f", "femto"), (-18, "a", "atto"),
    (-21, "z", "zepto"), (-24, "y", "yocto"), (-27, "r", "ronto"),
    (-30, "q", "quecto"),
)
# Only reachable in mode="full_si": these break the powers-of-1000 cadence.
_SI_FULL_MULTIPLES: tuple[tuple[int, str, str], ...] = (
    (2, "h", "hecto"), (1, "da", "deka"),
)
_SI_FULL_SUBMULTIPLES: tuple[tuple[int, str, str], ...] = (
    (-1, "d", "deci"), (-2, "c", "centi"),
)
_IDENTITY: tuple[int, str, str] = (0, "", "")
_IEC_MULTIPLES: tuple[tuple[int, str, str], ...] = (
    (100, "Qi", "quebi"), (90, "Ri", "robi"), (80, "Yi", "yobi"),
    (70, "Zi", "zebi"), (60, "Ei", "exbi"), (50, "Pi", "pebi"),
    (40, "Ti", "tebi"), (30, "Gi", "gibi"), (20, "Mi", "mebi"),
    (10, "Ki", "kibi"),
)

_SYSTEMS = ("si", "iec")
_MODES = ("engineering", "full_si")

# Built tables, keyed by (system, mode, submultiples, ascii_micro).
_TABLE_CACHE: dict[tuple[str, str, bool, bool], tuple[tuple[float, str, str], ...]] = {}


def _decimal_factor(power: int) -> float:
    """Return 10**power as a float, without accumulating float exponentiation error.

    Args:
        power: Integer power of ten, positive or negative.

    Returns:
        The nearest float to 10**power.
    """
    if power >= 0:
        return float(10 ** power)
    return 1.0 / float(10 ** -power)


def _prefix_table(system: str, mode: str, *, submultiples: bool,
                  ascii_micro: bool) -> tuple[tuple[float, str, str], ...]:
    """Build the ordered (factor, symbol, long name) table for one configuration.

    Args:
        system:       "si" (powers of 1000) or "iec" (powers of 1024).
        mode:         "engineering" (powers of 1000 only) or "full_si"
                      (additionally deci/centi/deka/hecto).
        submultiples: Whether prefixes below 1 are available at all.
        ascii_micro:  Emit "u" instead of "µ" for micro.

    Returns:
        Entries sorted by descending factor, always including the unprefixed
        (factor 1.0) entry.
    """
    key = (system, mode, submultiples, ascii_micro)
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached

    if system == "iec":
        entries = [(float(2 ** power), symbol, long_name)
                   for power, symbol, long_name in _IEC_MULTIPLES]
        entries.append((1.0, "", ""))
    else:
        powers: list[tuple[int, str, str]] = list(_SI_MULTIPLES)
        if mode == "full_si":
            powers += list(_SI_FULL_MULTIPLES)
        powers.append(_IDENTITY)
        if submultiples:
            if mode == "full_si":
                powers += list(_SI_FULL_SUBMULTIPLES)
            powers += list(_SI_SUBMULTIPLES)
        powers.sort(key=lambda entry: entry[0], reverse=True)
        entries = [(_decimal_factor(power), symbol, long_name)
                   for power, symbol, long_name in powers]

    if ascii_micro:
        entries = [(factor, "u" if symbol == "µ" else symbol, long_name)
                   for factor, symbol, long_name in entries]

    table = tuple(entries)
    _TABLE_CACHE[key] = table
    return table


def _validate_system_mode(system: str, mode: str) -> None:
    """Reject unknown systems/modes and binary submultiple requests.

    Args:
        system: Prefix system name.
        mode:   Prefix mode name.

    Raises:
        ValueError: If `system` or `mode` is unknown, or if SI submultiple
            prefixes are requested for the binary (IEC) system.
    """
    if system not in _SYSTEMS:
        raise ValueError(
            f"unknown system {system!r}: expected one of {_SYSTEMS}"
        )
    if mode not in _MODES:
        raise ValueError(
            f"unknown mode {mode!r}: expected one of {_MODES}"
        )
    if system == "iec" and mode == "full_si":
        raise ValueError(
            "the binary (IEC) system has no submultiple prefixes: "
            "mode='full_si' is unavailable with system='iec' — "
            "use system='si' for values below 1"
        )


def _select(table: tuple[tuple[float, str, str], ...],
            magnitude: float) -> tuple[float, str, str]:
    """Return the table entry whose factor scales `magnitude` into [1, step).

    Values above the largest prefix or below the smallest clamp to that end of
    the table rather than overflowing it.

    Args:
        table:     Ordered prefix table from `_prefix_table`.
        magnitude: Non-negative, finite, non-zero magnitude.

    Returns:
        The chosen (factor, symbol, long name) entry.
    """
    for entry in table:
        if magnitude >= entry[0]:
            return entry
    return table[-1]


def choose_prefix(values: Iterable[float | int], unit: Unit | None = None, *,
                  system: str = "si", mode: str = "engineering",
                  ascii_micro: bool = False) -> tuple[str, float]:
    """Pick one prefix for a whole set of values, e.g. every tick on one axis.

    Formatting axis ticks one at a time gives "1 mm", "2 mm", "1 cm" — three
    scales on one axis. Instead, label the axis once with `<symbol><unit>` and
    divide every tick by the returned factor.

    The choice is driven by the largest finite magnitude in `values`; NaN and
    infinity are ignored, and an empty or all-zero set yields the unprefixed
    scale.

    Args:
        values:      Iterable of values, consumed once. May contain NaN/inf.
        unit:        The unit the values are expressed in. It does not affect
                     the chosen prefix — it is accepted so call sites read as
                     `choose_prefix(ticks, METERS)`, and so passing something
                     that is not a `Unit` fails immediately.
        system:      "si" for powers of 1000, "iec" for powers of 1024.
        mode:        "engineering" for powers of 1000 only, or "full_si" to
                     additionally allow deci, centi, deka and hecto.
        ascii_micro: Emit "u" instead of "µ" for micro.

    Returns:
        A (prefix symbol, divisor) pair. The unprefixed scale is ("", 1.0).

    Raises:
        TypeError:  If `unit` is neither None nor a `Unit`.
        ValueError: If `system` or `mode` is unknown, or submultiples are
            requested for the binary system.

    Example:
        >>> choose_prefix([0.001, 0.002, 0.011], METERS, mode="full_si")
        ('c', 0.01)
    """
    if unit is not None and not isinstance(unit, Unit):
        raise TypeError(f"unit must be a Unit or None, got {type(unit).__name__}")
    _validate_system_mode(system, mode)
    table = _prefix_table(system, mode, submultiples=system == "si",
                          ascii_micro=ascii_micro)

    largest = 0.0
    for value in values:
        magnitude = abs(float(value))
        if math.isfinite(magnitude) and magnitude > largest:
            largest = magnitude
    if largest == 0.0:
        return ("", 1.0)

    factor, symbol, _ = _select(table, largest)
    return (symbol, factor)


def _format_quantity(num: float | int | None, unit: Unit, *, system: str, mode: str,
                     precision: int, space: bool, trim_trailing_zeros: bool,
                     long_units: bool, ascii_micro: bool, submultiples: bool,
                     promote: bool, clamp_non_finite: bool) -> str:
    """Shared formatting machinery behind `human_quantity` and `human_bytesize`.

    Args:
        num:                 Value to format, or None.
        unit:                Unit whose symbol and long names are appended.
        system:              "si" or "iec"; already validated by the caller.
        mode:                "engineering" or "full_si"; already validated.
        precision:           Decimal places, or a negative total width.
        space:               Insert a space between number and unit.
        trim_trailing_zeros: Strip trailing zeros and any dangling point.
        long_units:          Spell prefix and unit out in words.
        ascii_micro:         Emit "u" instead of "µ" for micro.
        submultiples:        Allow prefixes below 1.
        promote:             Re-check the prefix after rounding, so a value that
                             rounds up to the next step moves up a prefix.
        clamp_non_finite:    Legacy `human_bytesize` behaviour: let infinity walk
                             the table and clamp to the largest prefix, instead
                             of formatting it unprefixed.

    Returns:
        The formatted string.

    Raises:
        ValueError: In width-constrained mode, when the requested width cannot
            hold the unit plus at least one digit.
    """
    if num is None:
        return "None"

    table = _prefix_table(system, mode, submultiples=submultiples,
                          ascii_micro=ascii_micro)
    sign = "-" if num < 0 else ""
    magnitude = abs(float(num))

    if math.isnan(magnitude) or (not math.isfinite(magnitude)
                                 and not clamp_non_finite) or magnitude == 0.0:
        factor, symbol, long_prefix = 1.0, "", ""
    else:
        factor, symbol, long_prefix = _select(table, magnitude)
    scaled = magnitude / factor

    if precision < 0:
        return _format_width_constrained(
            scaled, sign=sign, symbol=symbol, unit=unit, precision=precision,
            space=space, trim_trailing_zeros=trim_trailing_zeros, system=system,
        )

    text = f"{scaled:.{precision}f}"

    if promote and magnitude and math.isfinite(magnitude):
        # Rounding can push the value onto the next prefix ("1000.0 k" -> "1.0 M").
        promoted = _select(table, float(text) * factor)
        if promoted[0] != factor:
            factor, symbol, long_prefix = promoted
            text = f"{magnitude / factor:.{precision}f}"

    if trim_trailing_zeros and "." in text:
        text = text.rstrip("0").rstrip(".")

    if long_units:
        word = unit.singular if text == "1" else unit.plural
        return f"{sign}{text} {long_prefix}{word}"
    separator = " " if space else ""
    return f"{sign}{text}{separator}{symbol}{unit.symbol}"


def _format_width_constrained(scaled: float, *, sign: str, symbol: str, unit: Unit,
                              precision: int, space: bool, trim_trailing_zeros: bool,
                              system: str) -> str:
    """Format into an exact total width, maximizing decimal places.

    Args:
        scaled:              Magnitude already divided by the prefix factor.
        sign:                "-" for negative values, else "".
        symbol:              Chosen prefix symbol.
        unit:                Unit supplying the trailing symbol.
        precision:           Negative; `-precision` is the total width.
        space:               Insert a space between number and unit.
        trim_trailing_zeros: Strip trailing zeros and any dangling point.
        system:              Reported in the error message.

    Returns:
        A string of exactly `-precision` characters.

    Raises:
        ValueError: If the width leaves no room for digits, or cannot hold even
            the integer form of the value.
    """
    total_width = -precision
    separator = " " if space else ""
    unit_text = f"{symbol}{unit.symbol}"

    # Remaining width available for the numeric portion (including sign/decimal point)
    numeric_width = total_width - len(separator) - len(unit_text)
    if numeric_width <= 0:
        raise ValueError(
            f"precision={precision} is too small: no room for numeric part "
            f"(unit='{unit_text}', space={space})"
        )

    # Fit the numeric part into numeric_width, maximizing decimals.
    # Right-justify so decimal points line up across values of the same width.
    for decimals in range(numeric_width, -1, -1):
        text = f"{scaled:.{decimals}f}"
        if trim_trailing_zeros and "." in text:
            text = text.rstrip("0").rstrip(".")

        candidate = f"{sign}{text}"
        if len(candidate) <= numeric_width:
            return f"{candidate.rjust(numeric_width)}{separator}{unit_text}"

    # Even integer form doesn't fit (e.g., 1023 MiB into a 3-char numeric field).
    integer_text = f"{scaled:.0f}"
    min_needed = len(sign) + len(integer_text) + len(separator) + len(unit_text)
    raise ValueError(
        f"precision={precision} is too small for this value; "
        f"need at least {-min_needed} or less (space={space}, si={system == 'si'})"
    )


def human_quantity(num: float | int | None, unit: Unit, *, system: str = "si",
                   mode: str = "engineering", precision: int = 1, space: bool = True,
                   trim_trailing_zeros: bool = False, long_units: bool = False,
                   ascii_micro: bool = False) -> str:
    """Format one value with the prefix that scales it into [1, step).

    Args:
        num:                 The value. Negative values keep a leading minus.
                             If None, returns "None". NaN and infinity are
                             rendered unprefixed ("nan m", "-inf m").
        unit:                Unit to append, e.g. `METERS` or `JOULES`.
        system:              "si" for powers of 1000 with SI prefixes, or "iec"
                             for powers of 1024 with binary prefixes. The binary
                             system has no submultiples, so values below 1 stay
                             unprefixed there.
        mode:                "engineering" (default) restricts prefixes to powers
                             of 1000, so 0.02 m is "20.0 mm". "full_si" also
                             allows deci, centi, deka and hecto, so 0.02 m is
                             "2.0 cm".
        precision:           If >= 0, digits after the decimal point.
                             If < 0, constrains the total returned string length
                             to `-precision` (width-constrained mode;
                             `long_units` is ignored).
        space:               Insert a space between number and unit (ignored when
                             `long_units` is True, which always uses one space).
        trim_trailing_zeros: Remove trailing zeros and any dangling decimal point.
        long_units:          Spell prefix and unit out ("1.5 kilometers",
                             "1.5 kibibytes"). The unit's singular form is used
                             when the formatted number reads exactly "1".
        ascii_micro:         Emit "u" instead of "µ" for micro.

    Returns:
        A string such as "3.2 ZJ", "2.0 cm", "1.5 KiB" or "1.5 kilometers".

    Raises:
        TypeError:  If `unit` is not a `Unit`.
        ValueError: If `system` or `mode` is unknown, if submultiples are
            requested for the binary system, or if a width-constrained request
            cannot fit.

    Example:
        >>> human_quantity(3.2e21, JOULES)
        '3.2 ZJ'
        >>> human_quantity(0.02, METERS, mode="full_si")
        '2.0 cm'
    """
    if not isinstance(unit, Unit):
        raise TypeError(f"unit must be a Unit, got {type(unit).__name__}")
    _validate_system_mode(system, mode)
    return _format_quantity(
        num, unit, system=system, mode=mode, precision=precision, space=space,
        trim_trailing_zeros=trim_trailing_zeros, long_units=long_units,
        ascii_micro=ascii_micro, submultiples=system == "si", promote=True,
        clamp_non_finite=False,
    )


def human_bytesize(num: float | int | None, *, suffix: str = "B", si: bool = False, precision: int = 1,
                   space: bool = True, trim_trailing_zeros: bool = False, long_units: bool = False) -> str:
    """
    Formats a byte count into a human-readable string.

    Args:
        num:                 Size in bytes. Negative values are preserved with a leading minus.
                             If None, returns "None".
        suffix:              Unit suffix appended after the prefix (defaults to "B"). If long_units is True and
                             suffix is "B", "bytes" is appended in the output. Otherwise, the suffix is appended to the long name.
        si:                  If True, use powers of 1000 with SI prefixes (k, M, G, ... up to R, Q).
                             If False, use powers of 1024 with IEC prefixes (Ki, Mi, Gi, ... up to Ri, Qi).
        precision:           If >= 0, digits to show after the decimal point.
                             If < 0, constrains the total returned string length to `-precision`
                             (width-constrained mode; `long_units` is forced False).
        space:               If True, inserts a space between the number and the unit (ignored when long_units is True).
        trim_trailing_zeros: If True, removes trailing zeros and any dangling decimal point.
        long_units:          If True, spell out unit names ("bytes", "kibibytes", ... "quebibytes"/"quettabytes").

    Returns:
        A concise string such as "1.5KiB", "1.5 kB", or "1.5 megabytes" depending on options.
        If num is None, returns "None".
        Handles negative values with a leading minus sign and units up to "quebibytes" (2^100 = 1024^10 bytes) for IEC,
        or "quettabytes" (10^30 bytes) for SI.

    Raises:
        None.
    """
    if num is None:
        return "None"
    # precision >= 0: decimal places mode
    # precision < 0: fixed total-width mode (handled in _format_width_constrained)
    if suffix and not isinstance(suffix, str):
        suffix = str(suffix)

    # Legacy long form is `<long prefix>bytes` for "B" and `<long prefix><suffix>`
    # otherwise, and never inflects, so singular and plural are the same word.
    long_word = "bytes" if suffix == "B" else suffix
    unit = Unit(suffix, long_word, long_word)

    # Three deliberate deviations from `human_quantity`, kept for byte-for-byte
    # compatibility with the published output: no submultiples (0.5 stays
    # "0.5 B"), no prefix promotion after rounding (999999 B stays "1000.0 kB"),
    # and infinity walks the table to the largest prefix ("inf QiB").
    return _format_quantity(
        num, unit, system="si" if si else "iec", mode="engineering",
        precision=precision, space=space,
        trim_trailing_zeros=trim_trailing_zeros, long_units=long_units,
        ascii_micro=False, submultiples=False, promote=False,
        clamp_non_finite=True,
    )

def sci_exp(x: float | int, max_digits: int = 15) -> int:
    """Return floor(log10(|x|)), clamped to -max_digits for very small |x|.
    For x == 0, returns -max_digits.
    """
    import math
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise TypeError("x must be an int or float (not bool)")
    if not math.isfinite(x):
        raise ValueError("x must be finite")
    if x == 0:
        return -max_digits
    exp = int(math.floor(math.log10(abs(x))))
    return max(exp, -max_digits)

def round_out(x: float, round_digits: int = 3, max_digits: int = 15) -> float:
    """
    Round a number away from zero (i.e. rounds up for x>0 and down for x<0) to
    the specified number of significant figures (defaults to 3).
    If the number is smaller than 10^(-max_digits), it will be returned as is.
    The max_digits parameter defaults to 15, but can be changed to a different value if needed.

    Args:
        x:             The number to round.
        round_digits:  The number of significant figures to round to (default is 3).
        max_digits:    The maximum number of digits to consider for very small numbers (default is 15).

    Returns:
        float: The rounded number, or the original number if it is smaller than 10^(-max_digits).
    """
    import numpy as np
    if np.abs(x) < 10**(-max_digits): return x
    these_digits = sci_exp(x) - round_digits + 1
    thisfactor = 10**these_digits
    x = x/thisfactor
    if x > 0: x = np.ceil(x)
    else:     x = np.floor(x)
    return x*(thisfactor*1.0)
