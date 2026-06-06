"""python_env — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from emmykit._version import PY_VERSION
from emmykit.options import Options
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import safe_is_file

def detect_shell(options: Options) -> None:
    """
    Detect the current interactive shell, falling back to parent process name if needed.

    Args:
        options: Options object to store the detected shell information.

    Returns:
        None, but updates options.shell with the detected shell name.

    Raises:
        None, but logs an error if the shell cannot be detected via
        subprocess.CalledProcessError or FileNotFoundError.
    """
    import subprocess
    shell_path = os.getenv("SHELL")
    if not shell_path:  # If shell_path is None or empty (""), try to get the parent process name
        try:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("SHELL environment variable not set, trying to detect shell from parent process.")
            ppid   = os.getppid()
            result = subprocess.run(["ps", "-p", str(ppid), "-o", "comm="],
                                    capture_output=True, text=True, check=True)
            shell_path = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"Error detecting shell via ps: {e}")
    if shell_path:
        options.shell = ensure_path(shell_path).name.lstrip("-")
    else:
        logging.error("Could not detect shell from SHELL environment variable or parent process.")
        options.shell = None

def find_shell_rc_file(options: Options) -> None:
    """
    Find the shell configuration file for the current user, store in options.rc_file.
    For bash/zsh, also consider login‐shell files if the usual rc isn't present.

    Args:
        options: Options object containing the shell type and rc_file attribute.

    Returns:
        None, but updates options.rc_file with the path to the shell configuration file.

    Raises:
        None, but logs an error if the shell is unsupported or if no rc file is found
        for the specified shell.
    """
    candidates = []

    xdg = Path(os.environ.get("XDG_CONFIG_HOME", options.home / ".config"))
    if options.shell == "bash":
        candidates = [".bashrc", ".bash_profile", ".bash_login", ".profile"]
    elif options.shell == "zsh":
        candidates = [".zshrc", ".zprofile"]
    elif options.shell == "fish":
        candidates = [os.fspath(xdg / "fish" / "config.fish")]  # just to be consistent with the other strings.
    elif options.shell == "csh":
        candidates = [".cshrc"]
    elif options.shell == "tcsh":
        candidates = [".tcshrc"]
    else:
        logging.error(f"Unsupported shell: {options.shell}")
        options.rc_file = None
        return

    # pick the first one that actually exists
    for fname in candidates:
        path = options.home / fname
        if safe_is_file(path):
            options.rc_file = path
            break
    else:
        options.rc_file = None
        logging.error("No existing rc file found for %s shell in %s. Tried: %s.",
                      options.shell, options.home, ", ".join(candidates))

def find_additional_alias_files(options: Options) -> None:
    """Find additional alias files for the shell."""
    # Define common potential additional alias files based on the shell type.
    if options.shell == "bash":
        options.additional_alias_files.append(options.home / ".bash_aliases")
    elif options.shell == "zsh":
        options.additional_alias_files.append(options.home / ".zsh_aliases")
    elif options.shell == "fish":
        options.additional_alias_files.append(options.home / ".config" / "fish" / "conf.d" / "aliases.fish")
    elif options.shell == "csh":
        options.additional_alias_files.append(options.home / ".csh_aliases")
    elif options.shell == "tcsh":
        options.additional_alias_files.append(options.home / ".tcsh_aliases")
    else:
        logging.error(f"Unsupported shell for additional alias files: {options.shell}")
    valid_files = []
    for this_file in options.additional_alias_files:
        if safe_is_file(this_file):
            valid_files.append(this_file)
        else:
            logging.error(f"Additional alias file {this_file} does not exist for shell {options.shell}.")
    options.additional_alias_files = valid_files

def check_python_version(command: str) -> bool:
    """Check if the given Python command is available and has a version of PY_VERSION or higher."""
    import subprocess
    preferred_major = int(PY_VERSION)
    preferred_minor = int((PY_VERSION - preferred_major) * 100)
    result = subprocess.run([command, "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stdout.strip().split()[1]
        major, minor = map(int, version.split(".")[:2])
        if major == preferred_major and minor >= preferred_minor:
            return True
    return False

def find_preferred_python_version() -> str | None:
    """Find the command for the preferred version of python (stored here as PY_VERSION)."""
    # Check if the preferred python command (only specifying integer part of the preferred version) exists and returns a valid path
    import subprocess
    preferred_major       = int(PY_VERSION)
    preferred_python_path = subprocess.run(["which", f"python{preferred_major}"],
                                           capture_output=True, text=True).stdout.strip()
    if preferred_python_path and check_python_version(f"python{preferred_major}"):
        return os.path.basename(preferred_python_path)
    # Check if the preferred python command (with complete version specified) exists and returns a valid path
    preferred_python_path = subprocess.run(["which", f"python{PY_VERSION}"],
                                           capture_output=True, text=True).stdout.strip()
    if preferred_python_path and check_python_version(f"python{PY_VERSION}"):
        return os.path.basename(preferred_python_path)
    return None
