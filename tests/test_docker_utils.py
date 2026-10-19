"""`docker_utils`, with Docker replaced by a fake `my_popen`."""

from __future__ import annotations

import gc
import re
import shutil
import sys
import time
import types
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest

from emmykit import docker_utils


def test_build_command_is_read_from_the_dockerfile_and_the_file_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first-line comment is the build command; the Dockerfile is not left open."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("# docker build -t demo .\nFROM scratch\n", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_popen(cmd: list[str], *args: object, **kwargs: object) -> types.SimpleNamespace:
        commands.append(cmd)
        missing = cmd[:3] == ["docker", "image", "inspect"]
        return types.SimpleNamespace(success=not missing, stderr="")

    monkeypatch.setattr(docker_utils, "my_popen", fake_popen)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        docker_utils.ensure_image_built("demo", dockerfile=dockerfile)
        gc.collect()

    assert commands[-1][:2] == ["sh", "-c"] and commands[-1][2].endswith("&& docker build -t demo .")
    assert [w for w in caught if issubclass(w.category, ResourceWarning)] == []


# --- failures raise RuntimeError instead of exiting the process -------------

def _popen_returning(stderr: str, succeed: Callable[[list[str]], bool]) -> Callable[..., types.SimpleNamespace]:
    """A fake `my_popen` that succeeds for the commands `succeed` accepts and fails the rest with `stderr`."""
    def fake_popen(cmd: list[str], *args: object, **kwargs: object) -> types.SimpleNamespace:
        ok = succeed(cmd)
        return types.SimpleNamespace(success=ok, stderr="" if ok else stderr)
    return fake_popen


def test_missing_docker_cli_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `docker` on PATH is a RuntimeError naming the install page, not sys.exit."""
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match=r"^Docker CLI not found\. Please install Docker: https://docs\.docker\.com/get-docker/$"):
        docker_utils.ensure_docker_installed()


@pytest.mark.parametrize(
    ("platform", "succeed", "message"),
    [
        ("linux", lambda cmd: False, r"^Could not start Docker daemon:\nno sudo$"),
        ("darwin", lambda cmd: False, r"^Failed to launch Docker Desktop\. Please start it from your Applications folder\.$"),
        ("darwin", lambda cmd: cmd[:2] == ["open", "-a"],
         r"^Docker Desktop did not finish starting within 30 seconds\.\nPlease open Docker Desktop manually\.$"),
        ("win32", lambda cmd: False, r"^Unsupported OS for auto-starting Docker: win32$"),
    ],
    ids=["linux-start-fails", "darwin-launch-fails", "darwin-never-ready", "other-os"],
)
def test_daemon_that_cannot_be_started_raises(
    monkeypatch: pytest.MonkeyPatch, platform: str, succeed: Callable[[list[str]], bool], message: str
) -> None:
    """Each way of failing to start the daemon is a RuntimeError with its own message."""
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(docker_utils, "my_popen", _popen_returning("no sudo", succeed))

    with pytest.raises(RuntimeError, match=message):
        docker_utils.ensure_daemon_running()


def test_unreadable_dockerfile_raises_with_the_os_error_as_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Dockerfile that can't be opened is a RuntimeError chained to the OSError."""
    dockerfile = tmp_path / "Dockerfile"  # never created
    monkeypatch.setattr(docker_utils, "my_popen", _popen_returning("", lambda cmd: False))

    with pytest.raises(RuntimeError) as excinfo:
        docker_utils.ensure_image_built("demo", dockerfile=dockerfile)

    assert str(excinfo.value) == f"Cannot read {dockerfile} to build demo"
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


def test_dockerfile_without_a_build_comment_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first line that isn't a `#` comment is a RuntimeError, and nothing is built."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    commands: list[list[str]] = []
    fake = _popen_returning("", lambda cmd: False)
    monkeypatch.setattr(docker_utils, "my_popen", lambda cmd, *a, **k: (commands.append(cmd), fake(cmd))[1])

    with pytest.raises(RuntimeError, match=rf"^No build command found in {re.escape(str(dockerfile))}$"):
        docker_utils.ensure_image_built("demo", dockerfile=dockerfile)
    assert [c[0] for c in commands] == ["docker"]  # only the inspect ran


def test_failed_build_raises_with_the_build_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """A build command that fails is a RuntimeError carrying its stderr."""
    monkeypatch.setattr(docker_utils, "my_popen", _popen_returning("step 3/7 failed", lambda cmd: False))

    with pytest.raises(RuntimeError, match=r"^Failed to build demo:\nstep 3/7 failed$"):
        docker_utils.ensure_image_built("demo", build_cmd="docker build -t demo .")


def test_run_with_docker_fixes_passes_on_a_failing_fix(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a fix can't repair Docker, its RuntimeError reaches the caller instead of exiting."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(docker_utils, "my_popen", _popen_returning("docker: not found", lambda cmd: False))

    with pytest.raises(RuntimeError, match=r"^Docker CLI not found\."):
        docker_utils.run_with_docker_fixes(["docker", "run", "demo"])
