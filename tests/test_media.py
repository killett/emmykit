"""`emmykit.media`: `set_system_volume` falling back to pactl (pulsectl and pactl faked), and `find_ffmpeg`."""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from emmykit.media import find_ffmpeg, set_system_volume

# What `pactl get-sink-volume` prints for a sink at 50%.
PACTL_AT_50 = (
    "Volume: front-left: 32768 /  50% / -18.06 dB,   "
    "front-right: 32768 /  50% / -18.06 dB\n"
)


@pytest.fixture
def pactl_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Answer pactl commands as a sink at 50% would, and record them; run on "Linux"."""
    calls: list[list[str]] = []

    def run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert cmd[0] == "pactl"
        calls.append(cmd)
        stdout = PACTL_AT_50 if cmd[1] == "get-sink-volume" else ""
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys, "platform", "linux")
    return calls


def test_falls_back_to_pactl_when_pulsectl_cannot_load(
    monkeypatch: pytest.MonkeyPatch, pactl_calls: list[list[str]]
) -> None:
    """pulsectl installed but libpulse missing: pactl sets the volume instead.

    Fails with UnboundLocalError if the `except PulseError` clause is reached
    before `PulseError` was imported.
    """
    def missing_libpulse(name: str) -> object:
        raise OSError("libpulse.so.0: cannot open shared object file")

    broken = types.ModuleType("pulsectl")
    broken.__getattr__ = missing_libpulse  # type: ignore[method-assign]
    monkeypatch.setitem(sys.modules, "pulsectl", broken)

    set_system_volume(50)

    assert ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "50%"] in pactl_calls


def test_falls_back_to_pactl_when_pulsectl_is_not_installed(
    monkeypatch: pytest.MonkeyPatch, pactl_calls: list[list[str]]
) -> None:
    """Without pulsectl at all, pactl sets the volume."""
    monkeypatch.setitem(sys.modules, "pulsectl", None)

    set_system_volume(50)

    assert ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "50%"] in pactl_calls


def test_stale_ffmpeg_variable_falls_through_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An FFMPEG variable naming a missing file is skipped with a warning.

    Fails if find_ffmpeg raises FileNotFoundError instead of trying PATH next.
    """
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    monkeypatch.setenv("FFMPEG", os.fspath(tmp_path / "gone" / "ffmpeg"))
    for key in ("FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", os.fspath(tmp_path))

    assert find_ffmpeg() == os.fspath(ffmpeg)
    assert "FFMPEG" in caplog.text
