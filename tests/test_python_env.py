"""`python_env` and `MIN_PYTHON_VERSION`, against stub interpreters on a private PATH.

Each stub is a shell script that prints "<major> <minor>" the way the real
probe (`sys.version_info[0], sys.version_info[1]`) does. PATH holds only the
stub folder, so a stray `which` subprocess would fail to run.
"""

from __future__ import annotations

import os
import re
import stat
import sys
import time
import tomllib
from pathlib import Path

import pytest

from emmykit import python_env
from emmykit._version import MIN_PYTHON_VERSION
from emmykit.python_env import check_python_version

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="stub interpreters are POSIX shell scripts")

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


@pytest.fixture
def bindir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty folder that is the whole of PATH."""
    folder = tmp_path / "bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", os.fspath(folder))
    return folder


def _stub(bindir: Path, name: str, body: str) -> Path:
    """Write an executable /bin/sh script called `name` into `bindir`."""
    path = bindir / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _python(bindir: Path, name: str, version: tuple[int, int]) -> Path:
    """A stub interpreter that reports `version`."""
    return _stub(bindir, name, f"echo {version[0]} {version[1]}")


def test_min_python_version_is_the_requires_python_floor() -> None:
    """The constant is a (major, minor) int tuple equal to pyproject's `requires-python` lower bound."""
    spec = tomllib.loads(PYPROJECT.read_text())["project"]["requires-python"]
    match = re.fullmatch(r">=\s*(\d+)\.(\d+)", spec)
    assert match, f"requires-python {spec!r} is no longer a plain >=X.Y floor"

    assert MIN_PYTHON_VERSION == (int(match[1]), int(match[2]))
    assert type(MIN_PYTHON_VERSION) is tuple
    assert all(type(part) is int for part in MIN_PYTHON_VERSION)


@pytest.mark.parametrize(
    ("version", "minimum", "expected"),
    [
        ((3, 12), (3, 13), False),  # float maths read a 3.13 floor as minor 12
        ((3, 10), (3, 11), False),  # ... and 3.11 as minor 10
        ((3, 9), (3, 10), False),   # 3.10 as a float is 3.1
        ((3, 10), (3, 9), True),    # "3.10" < "3.9" as strings
        ((3, 12), (3, 12), True),   # the floor itself passes
        ((3, 11), (3, 12), False),  # one below it doesn't
        ((4, 0), (3, 12), True),    # no upper bound, even across a major version
    ],
)
def test_version_is_compared_as_a_tuple(
    bindir: Path, version: tuple[int, int], minimum: tuple[int, int], expected: bool
) -> None:
    """An interpreter passes when its (major, minor) is at or above the minimum."""
    _python(bindir, "python3", version)

    assert check_python_version("python3", minimum=minimum) is expected


def test_default_minimum_is_min_python_version(bindir: Path) -> None:
    """Without `minimum`, the floor is MIN_PYTHON_VERSION."""
    major, minor = MIN_PYTHON_VERSION
    _python(bindir, "at-floor", (major, minor))
    _python(bindir, "below-floor", (major, minor - 1))

    assert check_python_version("at-floor") is True
    assert check_python_version("below-floor") is False


def test_the_running_interpreter_is_probed_correctly() -> None:
    """A real Python passes at its own version and fails one minor version above it."""
    here = (sys.version_info[0], sys.version_info[1])

    assert check_python_version(sys.executable, minimum=here) is True
    assert check_python_version(sys.executable, minimum=(here[0], here[1] + 1)) is False


def test_missing_command_is_false(bindir: Path) -> None:
    """A command that isn't on PATH is False, not FileNotFoundError."""
    assert check_python_version("python3") is False


@pytest.mark.parametrize(
    "body",
    ["echo 3 12; exit 1", "echo Python", "echo 3 12 0", "true"],
    ids=["exit-status-1", "not-numbers", "three-numbers", "no-output"],
)
def test_interpreter_that_answers_badly_is_false(bindir: Path, body: str) -> None:
    """A probe that fails or prints something unexpected is False, not an exception."""
    _stub(bindir, "python3", body)

    assert check_python_version("python3", minimum=(3, 0)) is False


def test_interpreter_that_hangs_is_false_after_the_timeout(
    bindir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A probe that never finishes is given up on: False, well before the stub would exit."""
    _stub(bindir, "python3", "exec /bin/sleep 30")
    monkeypatch.setattr(python_env, "_PROBE_TIMEOUT_S", 0.5)

    start = time.monotonic()
    assert check_python_version("python3", minimum=(3, 0)) is False
    assert time.monotonic() - start < 10
