"""system — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os
import sys

from emmykit.constants import DEFAULT_ENCODING
from emmykit.logging_utils import fallback_logging_config, return_method_name
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import safe_exists, safe_is_dir


def check_if_command_exists(command: str) -> bool:
    """
    Check if a command exists on the system.

    Args:
        command: The command to check.

    Returns:
        True if the command exists, False otherwise.
    """
    import subprocess
    return subprocess.run(["which", command], capture_output=True).returncode == 0

def open_terminal_and_run_command(the_command: str, close_after: bool = False,
                                  maximize_window: bool = False) -> None:
    """Open a GNOME terminal, source ~/.bashrc (via bash -i), run the_command,
    and optionally close or keep the window open. Optionally, maximize it."""
    import subprocess
    fallback_logging_config()
    logging.info("Opening terminal and running '%s'...", the_command)
    terminal_args: list[str] = []
    if sys.platform.startswith("linux"):
        terminal_args = ["gnome-terminal"]
    else:
        raise NotImplementedError(f"The function {return_method_name()} is only implemented for Linux, not for {sys.platform}")
    # if maximize_window:  # Disabled because in Ubuntu this causes the title bar to disappear.
    #     # either of these works; here we use both for clarity
    #     terminal_args += ["--window", "--maximize"]
    # Now tell bash to run the command, then exit or hand off to an interactive shell
    if close_after:
        bash_cmd = f"{the_command}; exit"
    else:
        bash_cmd = f"{the_command}; exec bash"
    terminal_args += ["--", "bash", "-ic", bash_cmd]
    subprocess.Popen(terminal_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_effective_free_memory() -> float:
    """Return the "effective" free memory in bytes: free memory plus buffers plus cache."""
    if sys.platform.startswith("linux"):
        # NOTE: If your kernel supports MemAvailable, you could use that instead for a more accurate measure of usable memory
        info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts     = line.split()
                key       = parts[0].rstrip(":")
                value_kb  = int(parts[1])
                info[key] = value_kb

        mem_free_kb = info.get("MemFree", 0)
        buffers_kb  = info.get("Buffers", 0)
        cached_kb   = info.get("Cached",  0)

        effective_free_memory = (mem_free_kb + buffers_kb + cached_kb) * 1024
    else:
        effective_free_memory = 0.0  # to appease mypy
        raise NotImplementedError(f"The function {return_method_name()} is only implemented for Linux, not for {sys.platform}")
    return effective_free_memory

def kill_process(pname: str) -> None:
    """Kill a process by its name, then check if it is still running and retry if needed. Make sure the process name is unique to avoid killing unintended processes."""
    import time
    import signal
    import subprocess
    while True:
        # Find the process IDs of the given process name
        process_ids = []
        try:
            process_list = subprocess.check_output(["pgrep", "-f", pname]).decode(DEFAULT_ENCODING)
            process_ids  = process_list.splitlines()
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to find process with name {pname}. Make sure the process name is correct and unique: {e}") from e

        if process_ids:
            for pid in process_ids:
                print(f"Killing {pname} process with PID: {pid}")
                try:
                    os.kill(int(pid), signal.SIGTERM)  # Send SIGTERM to terminate the process
                    print(f"Sent SIGTERM to PID {pid}")
                except ProcessLookupError as e:
                    raise ValueError(f"Process with PID {pid} not found. It may have already exited: {e}") from e
        else:
            print(f"No {pname} process found.")
            break

        # Check if the process is still running
        time.sleep(2)  # Wait for 2 seconds before checking again
        process_ids = subprocess.check_output(["pgrep", "-f", pname]).decode(DEFAULT_ENCODING).splitlines()

        if not process_ids:
            print(f"{pname} process successfully killed.")
            break  # Exit the loop when the process is no longer running
        else:
            print(f"{pname} is still running. Retrying...")

def is_process_running(process_name: str) -> bool:
    """Check if a process with the given name is running."""
    import subprocess
    fallback_logging_config()
    try:
        the_command = ["pgrep", "-f", process_name]
        results = subprocess.run(the_command, capture_output=True, text=True)
        if results.returncode != 0:
            return False
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred: {e}")
        return False

def start_only_one_instance(process_name: str) -> None:
    """Start a process, but only if it's not already running."""
    import subprocess
    import time
    fallback_logging_config()
    if not is_process_running(process_name):
        logging.info("Starting %s...", process_name)
        subprocess.Popen([process_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait briefly to ensure the command is processed
        time.sleep(1)
    else:
        logging.info("%s is already running.", process_name)

def open_filemanager_with_dirs(directories: list[str | os.PathLike[str]]) -> None:
    """
    Open the file manager with the specified directories.
    Note: Most file managers don't support multiple tabs via command line, so open separate windows.
    """
    import subprocess
    import time
    fallback_logging_config()
    if sys.platform.startswith("linux"):
        filemanager_command = "nemo"
    else:
        filemanager_command = ""  # to appease mypy
        logging.error(f"The function {return_method_name()} is only implemented for Linux systems, not for {sys.platform}")
        return
    logging.info("Opening file manager with specified directories...")
    for directory in directories:
        directory = ensure_path(directory)
        if not safe_exists(directory):
            logging.error(f"Directory {os.fspath(directory)} does not exist. Skipping.")
            continue
        if not safe_is_dir(directory):
            logging.error(f"Directory {os.fspath(directory)} is not a valid directory. Skipping.")
            continue
        subprocess.Popen([filemanager_command, os.fspath(directory)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        # Optional: Wait briefly between opening directories
        time.sleep(0.5)

def detect_country(force_wtfismyip: bool = False) -> str | None:
    """
    Detect the country of the IP address using ipinfo.io service.
    If the request fails, it falls back to wtfismyip.com service.

    Args:
        force_wtfismyip: If True, always use wtfismyip.com

    Returns:
        The country name as a string, or None if detection fails.

    Raises:
        ValueError: If the IPINFO_API_TOKEN environment variable is not set.
    """
    import subprocess
    import requests
    import json
    thecountryname = None
    if not force_wtfismyip:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("force_wtfismyip=%s.", force_wtfismyip)
        try:
            if "IPINFO_API_TOKEN" in os.environ:
                ipinfo_access_token = os.environ['IPINFO_API_TOKEN']
            else:
                raise ValueError("IPINFO_API_TOKEN environment variable is not set. If you don't have one, you can sign up for a free account here: https://ipinfo.io/signup")

            logging.info("Attempting to detect country using IPinfo...")
            # Uncomment the following lines if you want to use the ipinfo library instead of curl
            # import ipinfo
            # handler = ipinfo.getHandler(ipinfo_access_token,
            #                             request_options={"timeout": ipinfo_timeout_seconds})
            # details = handler.getDetails()
            # if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("IPinfo DETAILS:\n%s", details)
            # thecountryname = details.country
            the_command = ["curl", f"https://api.ipinfo.io/lite/8.8.8.8?token={ipinfo_access_token}"]
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Running command: %s", " ".join(the_command))
            result = subprocess.run(the_command, capture_output=True,
                                    text=True, timeout=5)
            if result.returncode != 0:
                logging.error("curl command failed with return code %d", result.returncode)
                raise Exception("Curl command failed")
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("curl output: %s", result.stdout)
            dct = json.loads(result.stdout)
            thecountryname = dct.get("country", "")
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Detected country from curl: %s", thecountryname)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            logging.warning("IPinfo exception: %s\nFalling back to wtfismyip.com.", e)

    if not thecountryname:
        try:
            resp = requests.get("https://wtfismyip.com/json", timeout=5)
            resp.raise_for_status()
            dct = resp.json()
            thecountryname = dct.get("YourFuckingCountry", "")
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Detailed results: %s", dct)
        except requests.exceptions.RequestException as e:
            logging.error("Country detection failed (network error): %s", e)
            return None
        except (ValueError, KeyError) as e:
            logging.error("Country detection failed (bad response): %s", e)
            return None

    return thecountryname.strip() if thecountryname else None
