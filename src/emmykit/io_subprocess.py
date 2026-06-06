"""io_subprocess — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import sys

from emmykit.extensions import (
    ARCHIVE_EXTENSIONS_SET,
    AUDIO_EXTENSIONS_SET,
    IMAGE_EXTENSIONS_SET,
    TEXT_ENCODINGS,
    VIDEO_EXTENSIONS_SET,
)
from emmykit.logging_utils import fallback_logging_config
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import safe_exists, safe_is_file, safe_size

def my_critical_error(message: str = "A critical error occurred.",
                      choose_breakpoint: bool = False,
                      exit_code: int = 1) -> None:
    """Log a critical error message and either exit the program or enter a breakpoint."""
    fallback_logging_config()
    # Determine if an exception is being handled:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if exc_type:
        # An exception is being handled; include exception info
        logging.critical(message, exc_info=True)
    else:
        # No exception is being handled; log only the message
        logging.critical(message)
    if choose_breakpoint:
        print("Entering breakpoint while inside the my_critical_error() function. You can step outside of this function and remain paused by pressing 'n' to access variables in the calling function or press 'c' to continue running the script. If logging is enabled but the level is not set to DEBUG, you can type logging.getLogger().setLevel(logging.DEBUG) to see more detailed logs.")
        breakpoint()
    else:
        sys.exit(exit_code)

class MyPopenResult:
    """A class to store the results of a customized subprocess.Popen call."""

    def __init__(self, stdout: str, stderr: str, returncode: int) -> None:
        """Initialize the MyPopenResult with stdout, stderr, and returncode."""
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.success = (returncode == 0)

def my_popen(command_list: list, suppress_info: bool = False,
             suppress_error: bool = False) -> MyPopenResult:
    """Execute a command using subprocess.Popen and capture the output line by line using threads."""
    import threading
    import subprocess
    import shlex
    fallback_logging_config(log_level=logging.INFO if not suppress_info else logging.ERROR)
    command_list_str = [str(item) for item in command_list]
    the_statement = "Executing command: " + " ".join(shlex.quote(str(arg)) for arg in command_list_str)
    if not suppress_info:
        logging.info(the_statement)
    else:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(the_statement)

    try:
        process = subprocess.Popen(
            command_list_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line-buffered
        )

        stdout_lines = []
        stderr_lines = []

        def read_stdout() -> None:
            """Read stdout line by line and log it."""
            if process.stdout is None:
                return
            for line in process.stdout:
                stdout_lines.append(line)
                log_line = line.strip()
                if not suppress_info:
                    logging.info(log_line)
                else:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(log_line)

        def read_stderr() -> None:
            """Read stderr line by line and log it."""
            if process.stderr is None:
                return
            for line in process.stderr:
                stderr_lines.append(line)
                log_line = line.strip()
                if not suppress_error:
                    logging.error(log_line)
                elif not suppress_info:
                    logging.info(log_line)
                else:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(log_line)

        # Start threads
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process and threads to finish
        process.wait()
        stdout_thread.join()
        stderr_thread.join()

        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)

        return MyPopenResult(stdout=stdout, stderr=stderr, returncode=process.returncode)

    except Exception as e:  # I don't want any exception here to crash the script, so I catch it and return a MyPopenResult with an error message.
        if not suppress_error:
            logging.error("An error occurred while executing the command '%s'", command_list_str, exc_info=True)
        else:
            logging.info("An error occurred while executing the command '%s'", command_list_str, exc_info=True)
        return MyPopenResult(stdout="", stderr=str(e), returncode=-1)

def my_fopen(file_path: str | os.PathLike[str],
             suppress_errors: bool = False,
             rawlog:          bool = False,
             numlines:  int | None = None,
             verbose:         bool = True) -> str | None:
    """
    Attempt to read a text file with various encodings and return the file content if successful. Optionally, specify numlines to limit the number of lines read.

    Args:
        file_path:       Path to the file to read.
        suppress_errors: If True, suppress error messages by logging them as info instead of as error.
        rawlog:          If True, use a simple log format without timestamps or levels.
        numlines:        If specified, read only this many lines from the file and return them as a string.
        verbose:         If True, log messages about the file reading process (default: True).

    Returns:
        The content of the file as a string, or:
        Returns None:
         - if the file does not exist
         - is empty
         - is a non-text file (video, audio, image, archive)
         - cannot be read with any of the specified encodings
    """
    fallback_logging_config(log_level=logging.INFO if not suppress_errors else logging.CRITICAL,
                            rawlog=rawlog)
    file_path = ensure_path(file_path)
    if not safe_exists(file_path):
        if verbose:
            this_message = f"File does not exist: {os.fspath(file_path)}"
            if not rawlog:
                if not suppress_errors: logging.error(this_message)
                else:                   logging.info( this_message)
        return None
    if not safe_is_file(file_path):
        if verbose:
            this_message = f"Path is a directory, not a file: {os.fspath(file_path)}"
            if not rawlog:
                if not suppress_errors: logging.error(this_message)
                else:                   logging.info( this_message)
        return None
    if (file_path_size := safe_size(file_path)) is None:
        if verbose:
            this_message = f"Could not determine file size: {os.fspath(file_path)}"
            if not rawlog:
                if not suppress_errors: logging.error(this_message)
                else:                   logging.info( this_message)
        return None
    if file_path_size == 0:
        if verbose:
            this_message = f"File is empty: {os.fspath(file_path)}"
            if not rawlog:
                if not suppress_errors: logging.error(this_message)
                else:                   logging.info( this_message)
        return None
    # Does the file extension match any of these (non-text) extensions?
    casefolded_suffix = file_path.suffix.casefold()
    if casefolded_suffix in VIDEO_EXTENSIONS_SET:
        if verbose and not rawlog:
            this_message = f"Skipping video file {os.fspath(file_path)}"
            if not suppress_errors: logging.error(this_message)
            else:                   logging.info( this_message)
        return None
    if casefolded_suffix in AUDIO_EXTENSIONS_SET:
        if verbose and not rawlog:
            this_message = f"Skipping audio file {os.fspath(file_path)}"
            if not suppress_errors: logging.error(this_message)
            else:                   logging.info( this_message)
        return None
    if casefolded_suffix in IMAGE_EXTENSIONS_SET:
        if verbose and not rawlog:
            this_message = f"Skipping image file {os.fspath(file_path)}"
            if not suppress_errors: logging.error(this_message)
            else:                   logging.info( this_message)
        return None
    if casefolded_suffix in ARCHIVE_EXTENSIONS_SET:
        if verbose and not rawlog:
            this_message = f"Skipping archive file {os.fspath(file_path)}"
            if not suppress_errors: logging.error(this_message)
            else:                   logging.info( this_message)
        return None
    for encoding in TEXT_ENCODINGS:  # use the (ordered) tuple so more common encodings are tried first.
        try:
            with open(file_path, "r", encoding=encoding) as file:
                if numlines is None:
                    file_content = file.read()
                else:
                    file_content = "".join(file.readline() for _ in range(numlines))
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Successfully read %s with encoding %s", os.fspath(file_path), encoding)
            return file_content  # Exit the function if reading is successful
        except UnicodeDecodeError:
            if verbose and not rawlog:
                this_message = f"Unicode decode error with encoding {encoding} reading file {os.fspath(file_path)}"
                if not suppress_errors: logging.warning(this_message, exc_info=True)
                else:                   logging.info(   this_message, exc_info=True)
            continue
        except LookupError:
            if verbose and not rawlog:
                this_message = f"Unknown codec {encoding} for file {os.fspath(file_path)}"
                if not suppress_errors: logging.warning(this_message, exc_info=True)
                else:                   logging.info(   this_message, exc_info=True)
            continue
        except Exception:  # Catch any other exceptions that might occur, but don't crash.
            if verbose and not rawlog:
                this_message = f"Error reading file {os.fspath(file_path)} with encoding {encoding}."
                if not suppress_errors: logging.error(this_message, exc_info=True)
                else:                   logging.info( this_message, exc_info=True)
            return None
    return None
