"""humanize — extracted from univ_defs.py."""

from __future__ import annotations


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
    # precision < 0: fixed total-width mode (handled below)
    if suffix and not isinstance(suffix, str):
        suffix = str(suffix)
    step = 1000.0 if si else 1024.0
    # SI prefixes: 10^N, N =  0,   3 ,   6 ,   9 ,  12 ,  15 ,  18 ,  21 ,  24 ,  27 ,  30
    symbols = ([             "", "k" , "M" , "G" , "T" , "P" , "E" , "Z" , "Y" , "R" , "Q" ]
               if si else [  "", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi", "Ri", "Qi"])
    # binary prefixes: 2^N, N=0,  10 ,  20 ,  30 ,  40 ,  50 ,  60 ,  70 ,  80 ,  90 ,  100

    long_prefixes = (
    # 10^N where N = 0,     3 ,     6 ,     9 ,    12 ,    15 ,    18 ,    21  ,     24 ,     27 ,      30
        [           "", "kilo", "mega", "giga", "tera", "peta", "exa" , "zetta", "yotta", "ronna", "quetta"]
        if si else ["", "kibi", "mebi", "gibi", "tebi", "pebi", "exbi", "zebi" , "yobi" , "robi" , "quebi" ])
    # 2^N where N =  0,    10 ,    20 ,    30 ,    40 ,    50 ,    60 ,    70  ,     80 ,     90 ,     100

    sign = "-" if num < 0 else ""
    n = abs(float(num))
    i = 0
    while n >= step and i < len(symbols) - 1:
        n /= step
        i += 1

    # Width-constrained mode: precision = -N means total output width must be N.
    if precision < 0:
        long_units = False  # forced off in width-constrained mode
        total_width = -precision

        sep = " " if space else ""
        unit = f"{symbols[i]}{suffix}"

        # Remaining width available for the numeric portion (including sign/decimal point)
        numeric_width = total_width - len(sep) - len(unit)
        if numeric_width <= 0:
            raise ValueError(
                f"precision={precision} is too small: no room for numeric part "
                f"(unit='{unit}', space={space})"
            )

        # Fit the numeric part into numeric_width, maximizing decimals.
        # Right-justify so decimal points line up across values of the same width.
        for dec in range(numeric_width, -1, -1):
            s_num = f"{n:.{dec}f}"
            if trim_trailing_zeros and "." in s_num:
                s_num = s_num.rstrip("0").rstrip(".")

            candidate_num = f"{sign}{s_num}"
            if len(candidate_num) <= numeric_width:
                return f"{candidate_num.rjust(numeric_width)}{sep}{unit}"

        # Even integer form doesn't fit (e.g., 1023 MiB into a 3-char numeric field).
        s_int = f"{n:.0f}"
        min_needed = len(sign) + len(s_int) + len(sep) + len(unit)
        raise ValueError(
            f"precision={precision} is too small for this value; "
            f"need at least {-min_needed} or less (space={space}, si={si})"
        )

    s = f"{n:.{precision}f}"

    if trim_trailing_zeros and "." in s:
        s = s.rstrip("0").rstrip(".")

    if long_units:
        long_name = long_prefixes[i]
        if suffix == "B":
            long_name += "bytes"
        else:
            long_name += suffix
        return f"{sign}{s} {long_name}"
    else:
        sep = " " if space else ""
        return f"{sign}{s}{sep}{symbols[i]}{suffix}"

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
