"""hosts — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import sys

from emmykit.logging_utils import fallback_logging_config, return_method_name

from typing import Final

def get_hostname_socket(rawlog: bool = False) -> str | None:
    """Retrieves the hostname using socket.gethostname()."""
    try:
        import socket
        return socket.gethostname()
    except Exception as e:
        if not rawlog: logging.warning("Failed to retrieve hostname using %s: %s", return_method_name(), e)
        return None

def get_hostname_platform(rawlog: bool = False) -> str | None:
    """Retrieves the hostname using platform.node()."""
    try:
        import platform
        return platform.node()
    except Exception as e:
        if not rawlog: logging.warning("Failed to retrieve hostname using %s: %s", return_method_name(), e)
        return None

def get_hostname_os_uname(rawlog: bool = False) -> str | None:
    """Retrieves the hostname using os.uname().nodename."""
    try:
        return os.uname().nodename
    except Exception as e:
        if not rawlog: logging.warning("Failed to retrieve hostname using %s: %s", return_method_name(), e)
        return None

def get_hostname_subprocess_hostname(rawlog: bool = False) -> str | None:
    """Retrieves the hostname using the 'hostname' system command via subprocess."""
    try:
        import subprocess
        result = subprocess.run(["hostname"], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        if not rawlog: logging.warning("Failed to retrieve hostname using %s: %s", return_method_name(), e)
        return None

def get_hostname_subprocess_scutil(rawlog: bool = False) -> str | None:
    """Retrieves the hostname using the 'scutil --get ComputerName' command on macOS via subprocess."""
    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(["scutil", "--get", "ComputerName"],
                                    capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as e:
            if not rawlog: logging.warning("Failed to retrieve hostname using %s: %s", return_method_name(), e)
    return None

def get_computer_name(rawlog: bool = False) -> str:
    """
    Attempts multiple methods to retrieve the computer's name and returns the most common one.

    Args:
        rawlog: If True, print statements are disabled.

    Returns:
        A string representing the most common computer name obtained from the methods.
        If no names were retrieved, returns "ERROR-NO-NAME".

    Raises:
        None: This function does not raise exceptions, but it may log warnings if no names are retrieved.
    """
    fallback_logging_config(rawlog=rawlog)
    methods = {
        "socket_gethostname"  : get_hostname_socket,
        "platform_node"       : get_hostname_platform,
        "os_uname_nodename"   : get_hostname_os_uname,
        "subprocess_hostname" : get_hostname_subprocess_hostname,
    }

    if sys.platform == "darwin":  # This next method is macOS-specific
        methods["subprocess_scutil_computername"] = get_hostname_subprocess_scutil

    results = {}

    for method_name, method_func in methods.items():
        try:
            name = method_func(rawlog=rawlog)
            if name:
                results[method_name] = name
        except Exception:  # Ignore all exceptions for individual methods
            if not rawlog: logging.exception("Method %s failed.", method_name)

    computer_name = analyze_computer_name_results(results, rawlog=rawlog)

    return computer_name

def analyze_computer_name_results(results: dict[str, str], rawlog: bool = False) -> str:
    """
    Analyzes the retrieved computer names.

    Args:
        results: Dictionary with method names as keys and computer names as values.
        rawlog:  If True, print statements are disabled.

    Returns:
        A string representing the most common computer name obtained from the methods.
        If no names were retrieved, returns "ERROR-NO-NAME".

    Raises:
        None: This function does not raise exceptions, but it may log errors or warnings if
              no names (or differing names) are retrieved.
    """
    from collections import Counter
    fallback_logging_config(rawlog=rawlog)

    if not results:
        if not rawlog: logging.error("No methods succeeded in retrieving the computer name.")
        return "ERROR-NO-NAME"

    name_values = list(results.values())
    name_counts = Counter(name_values)
    most_common = name_counts.most_common()

    if len(name_counts) == 1:
        # All names are identical
        if not rawlog: logging.info("Computer name: %s", most_common[0][0])
        return most_common[0][0]
    else:
        # Names are not identical
        primary_name, primary_count = most_common[0]
        differing = {name: count for name, count in most_common if name != primary_name}

        if not rawlog:
            the_string =   "Multiple computer names detected:\n"
            the_string += f" - Most common name: {primary_name} (appeared {primary_count} times)\n"
            the_string += f" - Other names: {', '.join(f'{name} ({count} times)' for name, count in differing.items())}\n"
            detailed_results_str = "\n".join(f"     - {method}: {name}" for method, name in results.items())
            the_string += f" - Detailed method outputs:\n{detailed_results_str}"
            logging.warning(the_string)

        return primary_name

COMPUTER_NAME: str = get_computer_name(rawlog=True)

NASA_COMPUTER_NAME_PREFIXES:            Final[tuple[str, ...]] = ("RAYL", "NASA", "JPL", "MT")

NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES: Final[tuple[str, ...]] = tuple(p.casefold() for p in
                                                                       NASA_COMPUTER_NAME_PREFIXES)

IS_NASA_COMPUTER: bool = COMPUTER_NAME.casefold().startswith(NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES)
