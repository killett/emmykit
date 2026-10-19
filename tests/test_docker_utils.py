"""`ensure_image_built`, with Docker replaced by a fake `my_popen`."""

from __future__ import annotations

import gc
import types
import warnings
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
