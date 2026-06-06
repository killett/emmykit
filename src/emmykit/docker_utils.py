"""docker_utils — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from emmykit.io_subprocess import MyPopenResult, my_critical_error, my_popen


def ensure_docker_installed() -> None:
    """Check if the Docker CLI is installed; if not, raise an error."""
    import shutil
    if shutil.which("docker") is not None:
        return
    my_critical_error("Docker CLI not found. Please install Docker: https://docs.docker.com/get-docker/")

def ensure_daemon_running() -> None:
    """Check if the Docker daemon is running; if not, attempt to start it."""
    info = my_popen(["docker", "info"])
    if info.success:
        return
    logging.info("Docker daemon not running; attempting to start it...")
    if sys.platform.startswith("linux"):
        start = my_popen(["sudo", "systemctl", "start", "docker"])
        if not start.success:
            start = my_popen(["sudo", "service", "docker", "start"])
        if not start.success:
            my_critical_error(f"Could not start Docker daemon:\n{start.stderr}")
    elif sys.platform == "darwin":
        launcher = my_popen(["open", "-a", "Docker"])
        if not launcher.success:
            my_critical_error("Failed to launch Docker Desktop. Please start it from your Applications folder.")
        # Wait for the daemon to start...
        import time
        for _ in range(10):
            time.sleep(3)
            info = my_popen(["docker", "info"])
            if info.success:
                logging.info("Docker daemon is running!")
                return
        my_critical_error("Docker Desktop did not finish starting within 30 seconds.\nPlease open Docker Desktop manually.")
    else:
        my_critical_error(f"Unsupported OS for auto-starting Docker: {sys.platform}")

def ensure_image_built(image: str, *,
                       dockerfile: Path | None = None,
                       build_dir:  Path | None = None,
                       build_cmd:   str | None = None) -> None:
    """
    Ensure that a Docker image with the given name exists; if not, build it.
    You can specify either a dockerfile (whose first line is a comment with the build command)
    or a build_cmd (and optionally a build_dir). If both dockerfile and build_cmd are None,
    the function will raise an error.
    """
    inspect = my_popen(["docker", "image", "inspect", image])
    if inspect.success:
        return

    if build_cmd is None:
        if dockerfile is None:
            raise ValueError(f"Image {image} missing and no build_cmd/dockerfile provided")
        try:
            first = open(dockerfile, "r").readline().strip()
        except OSError:
            my_critical_error(f"Cannot read {os.fspath(dockerfile)} to build {image}")
        if not first.startswith("#"):
            my_critical_error(f"No build command found in {os.fspath(dockerfile)}")
        build_cmd = first.lstrip("# ").strip()
        if build_dir is None:
            build_dir = dockerfile.parent

    # run build_cmd in build_dir
    import shlex
    full_cmd = f"cd {shlex.quote(os.fspath(build_dir or Path.cwd()))} && {build_cmd}"
    build = my_popen(["sh", "-c", full_cmd])
    if not build.success:
        my_critical_error(f"Failed to build {image}:\n{build.stderr}")

def run_with_docker_fixes(base_args: list[str], *,
                          ensure_build:         Callable[[], None]  | None = None,
                          extra_fixes: Iterable[Callable[[], None]] | None = None) -> MyPopenResult:
    """
    Run a command (typically 'docker run ...') and if it fails, attempt to fix
    common Docker issues (like Docker not installed or daemon not running) and retry.

    Args:
        base_args:    The command and its arguments to run (e.g., ['docker', 'run', ...]).
        ensure_build: An optional function to ensure a Docker image is built.
                      If provided, it will be called if the initial command fails.
        extra_fixes:  An optional iterable of additional fix functions to try if the command fails.

    Returns:
        The result of the successful command, or None if all fixes fail.

    Raises:
        RuntimeError: If all fixes fail and the command still does not succeed.
    """
    fixes = [ensure_docker_installed, ensure_daemon_running]
    if ensure_build is not None:
        fixes.append(ensure_build)
    if extra_fixes:
        fixes.extend(extra_fixes)

    last = None
    for fix in fixes:
        last = my_popen(base_args)
        if last.success:
            return last
        logging.info("docker run failed; attempting to fix: %s", fix.__name__)
        fix()

    last = my_popen(base_args)
    if last.success:
        return last
    raise RuntimeError(f"After applying all Docker fixes, still failed:\n{last.stderr}")
