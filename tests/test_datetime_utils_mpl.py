"""`AdaptiveDateFormatter` exercised through matplotlib itself.

The formatter's whole job is to see every tick at once, so the axis tests
install it on a real axis and draw rather than calling `format_ticks` by
hand: the 0.6.0 bug was invisible on that shortcut. matplotlib is an optional
dependency, so this file skips cleanly without it.
"""

from __future__ import annotations

import copy
import datetime as dt
import os
import pickle
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from matplotlib import dates as mdates  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib import ticker as mticker  # noqa: E402

import emmykit  # noqa: E402
from emmykit.datetime_utils import AdaptiveDateFormatter, Precision  # noqa: E402

# The span from the original report. `AutoDateLocator` ticks it every six
# months, on 1 January and 1 July, so year precision collides ("2021" twice)
# and month precision is the coarsest level that keeps every label unique.
SPAN_START = dt.datetime(2020, 10, 20)
SPAN_END = dt.datetime(2024, 11, 3)

# The directory holding the `emmykit` package these tests imported, so a
# subprocess imports the same copy rather than whatever else is installed.
SRC_DIR = Path(emmykit.__file__).resolve().parents[1]

# Custom levels that differ from the defaults only in their separator, so a
# formatter that lost its settings shows it as `2021-01` instead of `2021/01`.
SLASH_LEVELS = ["%Y", "%Y/%m", "%Y/%m/%d", "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S"]

# Two ticks that month precision tells apart: `2021/01` and `2021/07`.
JAN_AND_JUL_2021 = [mdates.date2num(dt.datetime(2021, 1, 1)),
                    mdates.date2num(dt.datetime(2021, 7, 1))]


def _bracketed_labels(self: AdaptiveDateFormatter, values: list[float]) -> list[str]:
    """`format_ticks` override for the subclasses below: the usual labels, bracketed.

    Calls `AdaptiveDateFormatter.format_ticks` by name rather than through
    `super()`, because in `FormatterFirst` matplotlib's own `format_ticks`
    comes first in the MRO.

    Args:
        self: The formatter.
        values: Tick values as matplotlib date numbers.

    Returns:
        One ``[label]`` per value.
    """
    return [f"[{label}]" for label in AdaptiveDateFormatter.format_ticks(self, values)]


def _suffixed_labels(self: AdaptiveDateFormatter, values: list[float]) -> list[str]:
    """`format_ticks` override: the usual labels with ``self.suffix`` appended.

    Args:
        self: The formatter, which must have a `suffix` attribute.
        values: Tick values as matplotlib date numbers.

    Returns:
        One label per value.
    """
    suffix = self.suffix  # type: ignore[attr-defined]
    return [label + suffix for label in AdaptiveDateFormatter.format_ticks(self, values)]


# The ways to subclass the formatter. Each must pickle and copy as itself.
# Only the first gets a class built at run time; the others already are
# `Formatter`s, so their instances keep the class as written.
class PlainSubclass(AdaptiveDateFormatter):
    """Lists only `AdaptiveDateFormatter`, as most subclasses would."""

    format_ticks = _bracketed_labels


class FormatterAfter(AdaptiveDateFormatter, mticker.Formatter):
    """Lists `Formatter` explicitly, after `AdaptiveDateFormatter`."""

    format_ticks = _bracketed_labels


class FormatterFirst(mticker.Formatter, AdaptiveDateFormatter):
    """Lists `Formatter` explicitly, before `AdaptiveDateFormatter`."""

    format_ticks = _bracketed_labels


class SubclassOfBuilt(type(AdaptiveDateFormatter())):  # type: ignore[misc]
    """Subclasses the run-time class an instance actually has."""

    format_ticks = _bracketed_labels


class WithSuffix(AdaptiveDateFormatter):
    """Adds a constructor keyword of its own, one without a default."""

    def __init__(self, *, suffix: str, **kwargs: Any) -> None:
        """Store `suffix` and pass the rest on.

        Args:
            suffix: Text appended to every label.
            **kwargs: `AdaptiveDateFormatter`'s own keywords.
        """
        super().__init__(**kwargs)
        self.suffix = suffix

    format_ticks = _suffixed_labels


class WithPositional(WithSuffix):
    """Takes its own parameter positionally."""

    def __init__(self, suffix: str, **kwargs: Any) -> None:
        """Pass `suffix` on by keyword.

        Args:
            suffix: Text appended to every label.
            **kwargs: `AdaptiveDateFormatter`'s own keywords.
        """
        super().__init__(suffix=suffix, **kwargs)


class Slotted(AdaptiveDateFormatter):
    """Keeps its own attribute in a slot rather than in ``__dict__``."""

    __slots__ = ("suffix",)

    def __init__(self, *, suffix: str, **kwargs: Any) -> None:
        """Store `suffix` and pass the rest on.

        Args:
            suffix: Text appended to every label.
            **kwargs: `AdaptiveDateFormatter`'s own keywords.
        """
        super().__init__(**kwargs)
        self.suffix = suffix

    format_ticks = _suffixed_labels


class WithLock(AdaptiveDateFormatter):
    """Holds a lock, which cannot be pickled, and leaves it out of its state."""

    def __init__(self, **kwargs: Any) -> None:
        """Create the lock and pass the keywords on.

        Args:
            **kwargs: `AdaptiveDateFormatter`'s own keywords.
        """
        super().__init__(**kwargs)
        self.lock = threading.Lock()

    def __getstate__(self) -> dict[str, Any]:
        """Return the instance state without the lock.

        Returns:
            A copy of ``__dict__`` minus `lock`.
        """
        state = self.__dict__.copy()
        del state["lock"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the state and give the copy a lock of its own.

        Args:
            state: What `__getstate__` returned.
        """
        self.__dict__.update(state)
        self.lock = threading.Lock()


class Registry(AdaptiveDateFormatter, mticker.Formatter):
    """Records its subclasses, and lists `Formatter` itself, as documented."""

    subclasses: list[type] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Record `cls`.

        Args:
            **kwargs: Class keywords, passed on.
        """
        super().__init_subclass__(**kwargs)
        Registry.subclasses.append(cls)


class Registered(Registry):
    """The one subclass `Registry` should ever record."""


@pytest.fixture(autouse=True)
def _close_figures() -> Iterator[None]:
    """Close every figure a test opened, pass or fail."""
    yield
    plt.close("all")


def _new_year_ticks(*years: int) -> list[float]:
    """Return matplotlib date numbers for 1 January of each given year.

    Args:
        *years: Calendar years.

    Returns:
        One matplotlib date float per year, in the order given.
    """
    return [mdates.date2num(dt.datetime(year, 1, 1)) for year in years]


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run `code` in a fresh interpreter that imports this checkout of emmykit.

    Args:
        code: Python source passed to `python -c`.

    Returns:
        The completed process, with text stdout and stderr captured.
    """
    path = [str(SRC_DIR), *filter(None, [os.environ.get("PYTHONPATH")])]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(path)}
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=120,
    )


def test_x_axis_keeps_the_formatter_and_draws_month_labels() -> None:
    """matplotlib must install the instance itself and hand it every tick.

    This is the 0.6.0 regression. The class was not a `Formatter`, so
    `set_major_formatter` wrapped it in a `FuncFormatter`, which asks for one
    label at a time; every tick fell back to day precision and the axis read
    `2021-01-01, 2021-07-01, ...`.
    """
    fig, ax = plt.subplots()
    ax.plot([SPAN_START, SPAN_END], [0, 1])
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fmt = AdaptiveDateFormatter()
    ax.xaxis.set_major_formatter(fmt)
    fig.canvas.draw()

    assert ax.xaxis.get_major_formatter() is fmt
    assert [t.get_text() for t in ax.get_xticklabels()] == [
        "2021-01", "2021-07", "2022-01", "2022-07", "2023-01",
        "2023-07", "2024-01", "2024-07", "2025-01",
    ]


def test_colorbar_keeps_the_formatter_and_draws_month_labels() -> None:
    """The same contract through a colorbar's axis, the other documented use.

    Fails the same way as the x-axis case: a wrapping `FuncFormatter` and
    `YYYY-MM-DD` labels down the colorbar.
    """
    fig, ax = plt.subplots()
    days = [SPAN_START + dt.timedelta(days=d)
            for d in range(0, (SPAN_END - SPAN_START).days, 30)]
    mappable = ax.scatter(range(len(days)), range(len(days)),
                          c=mdates.date2num(days))
    cbar = fig.colorbar(mappable)
    cbar.ax.yaxis.set_major_locator(mdates.AutoDateLocator())
    fmt = AdaptiveDateFormatter()
    cbar.ax.yaxis.set_major_formatter(fmt)
    fig.canvas.draw()

    assert cbar.ax.yaxis.get_major_formatter() is fmt
    assert [t.get_text() for t in cbar.ax.get_yticklabels()] == [
        "2021-01", "2021-07", "2022-01", "2022-07",
        "2023-01", "2023-07", "2024-01", "2024-07",
    ]


def test_instance_is_a_formatter_and_an_adaptive_date_formatter() -> None:
    """Both `isinstance` checks hold for an ordinary instance.

    Fails if the class is not a real `Formatter`, which is what lets
    matplotlib wrap it, or if the matplotlib-backed class an instance actually
    gets is no longer a subclass of the public name.
    """
    fmt = AdaptiveDateFormatter()

    assert isinstance(fmt, mticker.Formatter)
    assert isinstance(fmt, AdaptiveDateFormatter)


def test_max_precision_day_never_adds_a_time_even_when_days_collide() -> None:
    """Ticks six hours apart share a date, and the cap forbids adding a time.

    Fails if the constructor keywords are lost between `__new__` and
    `__init__`: the default cap of SECOND would then disambiguate these as
    `2024-03-15 00:00`, `2024-03-15 06:00`, and so on.
    """
    ticks = [mdates.date2num(dt.datetime(2024, 3, 15, hour))
             for hour in (0, 6, 12, 18)]
    fmt = AdaptiveDateFormatter(max_precision=Precision.DAY)

    assert fmt.format_ticks(ticks) == ["2024-03-15"] * 4


def test_min_precision_month_never_yields_a_bare_year() -> None:
    """New Year ticks are unique as bare years, but the floor is the month.

    Fails if `min_precision` is dropped on the way in: the default floor of
    YEAR would label these `2021`, `2022`, `2023`.
    """
    fmt = AdaptiveDateFormatter(min_precision=Precision.MONTH)

    assert fmt.format_ticks(_new_year_ticks(2021, 2022, 2023)) == [
        "2021-01", "2022-01", "2023-01",
    ]


def test_single_value_call_after_format_ticks_reuses_the_tick_label() -> None:
    """A per-value request for a tick matches the label drawn on the axis.

    On its own a single value is formatted at day precision, so this fails
    if `__call__` stops consulting what `format_ticks` computed: it would
    answer `2022-01-01` for a tick the axis labels `2022`.
    """
    fmt = AdaptiveDateFormatter()
    ticks = _new_year_ticks(2021, 2022, 2023)

    assert fmt.format_ticks(ticks) == ["2021", "2022", "2023"]
    assert fmt(ticks[1]) == "2022"


def test_figure_pickle_round_trip_keeps_the_formatter_and_its_settings() -> None:
    """A pickled figure comes back drawing the same adaptive labels.

    Fails if an instance pickles by its own class, which is built at run time
    and cannot be found by name (`PicklingError`, taking the whole figure
    with it), or if unpickling rebuilds the formatter with default settings,
    which would turn the slash-separated `2021/01` back into `2021-01`.
    """
    fig, ax = plt.subplots()
    ax.plot([SPAN_START, SPAN_END], [0, 1])
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(AdaptiveDateFormatter(format_levels=SLASH_LEVELS))

    restored = pickle.loads(pickle.dumps(fig))
    restored.draw_without_rendering()

    assert [t.get_text() for t in restored.axes[0].get_xticklabels()] == [
        "2021/01", "2021/07", "2022/01", "2022/07", "2023/01",
        "2023/07", "2024/01", "2024/07", "2025/01",
    ]


def test_formatter_built_from_type_of_another_pickles_with_its_settings() -> None:
    """`type(fmt)(...)` gives an ordinary formatter, not a doubly built one.

    `type(fmt)` is the run-time class, already a `Formatter`. Fails if
    construction wraps it in another run-time layer: the new instance's
    public class would then be the unimportable run-time one, and pickling
    raises `PicklingError`.
    """
    fmt = AdaptiveDateFormatter()
    clone = type(fmt)(format_levels=SLASH_LEVELS)

    assert type(clone) is type(fmt)
    restored = pickle.loads(pickle.dumps(clone))
    assert restored.format_ticks(_new_year_ticks(2021, 2022)) == ["2021", "2022"]
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["2021/01", "2021/07"]


def _pickle_round_trip(fmt: AdaptiveDateFormatter) -> AdaptiveDateFormatter:
    """Return `fmt` pickled and unpickled.

    Args:
        fmt: The formatter to round-trip.

    Returns:
        The unpickled copy.
    """
    return pickle.loads(pickle.dumps(fmt))


@pytest.mark.parametrize("duplicate", [_pickle_round_trip, copy.deepcopy],
                         ids=["pickle", "deepcopy"])
@pytest.mark.parametrize("cls", [PlainSubclass, FormatterAfter,
                                 FormatterFirst, SubclassOfBuilt],
                         ids=lambda cls: cls.__name__)
def test_subclass_comes_back_as_itself_with_its_settings(
    cls: type[AdaptiveDateFormatter],
    duplicate: Callable[[AdaptiveDateFormatter], AdaptiveDateFormatter],
) -> None:
    """A subclass instance survives pickling and copying with its overrides.

    Fails if the copy is rebuilt from the wrong class: in 0.6.2 a class that
    already was a `Formatter` came back as its first base, so
    `FormatterAfter` silently lost its override, `FormatterFirst` became a
    bare matplotlib `Formatter`, and `SubclassOfBuilt` could not be pickled
    at all. Also fails if the copy loses the slash-separated levels.
    """
    fmt = cls(format_levels=SLASH_LEVELS)

    restored = duplicate(fmt)

    assert type(restored) is type(fmt)
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["[2021/01]", "[2021/07]"]


def test_subclass_with_its_own_required_keyword_constructs_and_pickles() -> None:
    """A subclass may add a constructor keyword, even one without a default.

    Fails if `__new__` rejects keywords it does not know, as 0.6.1 and 0.6.2
    did (``TypeError: ... unexpected keyword argument 'suffix'``), or if
    unpickling calls the class with no arguments, which the missing required
    keyword turns into a `TypeError`.
    """
    fmt = WithSuffix(suffix=" UTC", format_levels=SLASH_LEVELS)

    restored = _pickle_round_trip(fmt)

    assert type(restored) is type(fmt)
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["2021/01 UTC", "2021/07 UTC"]


def test_subclass_with_a_positional_parameter_constructs_and_pickles() -> None:
    """A subclass may take its own parameter positionally.

    Fails if construction screens the arguments before the subclass's
    `__init__` sees them, as the `__new__` of 0.6.1 and 0.6.2 did
    (``TypeError: ... takes 1 positional argument but 2 were given``).
    """
    fmt = WithPositional(" UTC", format_levels=SLASH_LEVELS)

    restored = _pickle_round_trip(fmt)

    assert type(restored) is type(fmt)
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["2021/01 UTC", "2021/07 UTC"]


@pytest.mark.parametrize("duplicate", [_pickle_round_trip, copy.deepcopy],
                         ids=["pickle", "deepcopy"])
def test_subclass_slot_values_survive_pickle_and_deepcopy(
    duplicate: Callable[[AdaptiveDateFormatter], AdaptiveDateFormatter],
) -> None:
    """A value kept in ``__slots__`` comes back with the copy.

    Fails if pickling takes the state from ``__dict__`` alone, where slot
    values are not: the copy then has no `suffix` and its labels raise
    `AttributeError`.
    """
    fmt = Slotted(suffix=" UTC", format_levels=SLASH_LEVELS)

    restored = duplicate(fmt)

    assert type(restored) is type(fmt)
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["2021/01 UTC", "2021/07 UTC"]


@pytest.mark.parametrize("duplicate", [_pickle_round_trip, copy.deepcopy],
                         ids=["pickle", "deepcopy"])
def test_subclass_getstate_and_setstate_decide_what_is_copied(
    duplicate: Callable[[AdaptiveDateFormatter], AdaptiveDateFormatter],
) -> None:
    """A subclass's own state hooks run, so it can leave out a lock.

    The original's lock is held, so the copy can only take it at once if
    `__setstate__` gave it a fresh one. Fails if pickling ignores
    `__getstate__` and takes ``__dict__`` as it is (``TypeError: cannot
    pickle '_thread.lock' object``), or skips `__setstate__`.
    """
    fmt = WithLock(format_levels=SLASH_LEVELS)
    fmt.lock.acquire()

    restored = duplicate(fmt)

    assert type(restored) is type(fmt)
    assert restored.lock.acquire(blocking=False)
    assert restored.format_ticks(JAN_AND_JUL_2021) == ["2021/01", "2021/07"]


def test_subclass_listing_formatter_itself_gets_no_hidden_class() -> None:
    """The documented way to keep `__init_subclass__` hooks seeing real classes.

    A subclass that lists `Formatter` is used as it is. Fails if
    construction builds a run-time class for it anyway: the hook would
    record that class as a second subclass.
    """
    Registered()

    assert Registry.subclasses == [Registered]


def test_importing_emmykit_does_not_import_matplotlib() -> None:
    """The stdlib-only base stays stdlib-only, star import included.

    Fails for the naive fix, a module-level `class
    AdaptiveDateFormatter(Formatter)`, which would load matplotlib on every
    `import emmykit`; and for a lazy module attribute, which `import *` would
    resolve through `__all__`.
    """
    result = _run_python(
        "import sys\n"
        "import emmykit\n"
        "import emmykit.datetime_utils\n"
        "from emmykit import *\n"
        "print(sorted(m for m in sys.modules if m.partition('.')[0] == 'matplotlib'))\n"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_missing_matplotlib_raises_import_error_naming_the_extra() -> None:
    """Without matplotlib, emmykit imports and construction says what to install.

    A `None` entry in `sys.modules` makes every `import matplotlib...` fail,
    standing in for an install without the `datetime` extra. Fails if
    construction surfaces matplotlib's bare `ModuleNotFoundError`, which says
    nothing about emmykit's extras, or if the original error is not chained
    on, hiding the real cause when matplotlib is installed but broken.
    """
    result = _run_python(
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
