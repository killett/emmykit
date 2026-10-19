"""`kill_process`, with `pgrep`, `os.kill` and `time.sleep` replaced.

`pgrep` exits 0 with matching PIDs, 1 when nothing matches, and 2 or 3 when it
fails; the fake below follows that.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Iterator

import pytest

from emmykit.system import kill_process


def _fake_pgrep(monkeypatch: pytest.MonkeyPatch, results: list[str | int]) -> None:
    """Make successive `pgrep` calls print the given PIDs, or exit with the given code."""
    queue: Iterator[str | int] = iter(results)

    def check_output(cmd: list[str], *args: object, **kwargs: object) -> bytes:
        assert cmd[0] == "pgrep"
        result = next(queue)
        if isinstance(result, int):
            raise subprocess.CalledProcessError(result, cmd)
        return result.encode()

    monkeypatch.setattr(subprocess, "check_output", check_output)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


@pytest.fixture
def kills(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record the signals `kill_process` sends instead of sending them."""
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))
    return sent


def test_reports_success_once_the_process_is_gone(
    monkeypatch: pytest.MonkeyPatch, kills: list[tuple[int, int]], capsys: pytest.CaptureFixture[str]
) -> None:
    """After the kill, pgrep finding nothing means success, not an error.

    Fails if pgrep's "no match" exit status 1 escapes as CalledProcessError.
    """
    _fake_pgrep(monkeypatch, ["123\n", 1])

    kill_process("myproc")

    assert kills == [(123, signal.SIGTERM)]
    assert "myproc process successfully killed." in capsys.readouterr().out


def test_retries_while_the_process_is_still_running(
    monkeypatch: pytest.MonkeyPatch, kills: list[tuple[int, int]], capsys: pytest.CaptureFixture[str]
) -> None:
    """A process that survives SIGTERM is signalled again on the next round."""
    _fake_pgrep(monkeypatch, ["123\n", "123\n", "123\n", 1])

    kill_process("myproc")

    assert kills == [(123, signal.SIGTERM), (123, signal.SIGTERM)]
    assert "myproc is still running. Retrying..." in capsys.readouterr().out


def test_no_matching_process_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch, kills: list[tuple[int, int]], capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to kill prints a note and returns; nothing is signalled."""
    _fake_pgrep(monkeypatch, [1])

    kill_process("myproc")

    assert kills == []
    assert "No myproc process found." in capsys.readouterr().out


def test_pgrep_failure_raises_value_error(
    monkeypatch: pytest.MonkeyPatch, kills: list[tuple[int, int]]
) -> None:
    """A real pgrep failure (exit status 2 or 3) is still an error."""
    _fake_pgrep(monkeypatch, [2])

    with pytest.raises(ValueError, match="Failed to find process with name myproc"):
        kill_process("myproc")
    assert kills == []
