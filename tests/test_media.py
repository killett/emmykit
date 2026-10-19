"""`set_system_volume` falling back to pactl, with pulsectl and pactl faked."""

from __future__ import annotations

import subprocess
import sys
import types

import pytest

from emmykit.media import set_system_volume

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
