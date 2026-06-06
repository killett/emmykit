"""logging_utils — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from emmykit.paths_ensure import ensure_path

class MemoryHandler(logging.Handler):
    """A logging handler that stores logs in memory so the errors can be printed at the end."""

    def __init__(self, level: int = logging.ERROR) -> None:
        """Initialize the MemoryHandler with the specified logging level."""
        super().__init__(level)
        self.logs: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Capture the log record and store it in memory."""
        if record.levelno >= self.level:  # Only capture logs with the appropriate level
            self.logs.append(self.format(record))

class FlushingStreamHandler(logging.StreamHandler):
    """A logging handler that flushes the stream after emitting each log so the logs are immediately visible."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record and immediately flush the stream."""
        # Call the original emit method to handle the logging
        super().emit(record)
        # Immediately flush the stream after emitting the log
        self.flush()

class MaxLevelFilter(logging.Filter):
    """A logging filter that only allows logs up to a certain level to pass through, so that error messages aren't printed multiple times."""

    def __init__(self, max_level: int) -> None:
        """Initialize the MaxLevelFilter with the specified maximum logging level."""
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out log records above the maximum level."""
        return record.levelno <= self.max_level

def fallback_logging_config(log_level: int | str = logging.INFO, rawlog: bool = False) -> None:
    """
    Configure the root logger with a basic configuration if no handlers are set.
    Run this at the start of functions which might be run without first configuring logging.

    Args:
        level  : The logging level to set. Defaults to logging.INFO.
        rawlog : If True, use a simple log format without timestamps or levels.
    """
    if not logging.getLogger().handlers:
        if not rawlog:  # Use a full logging format with timestamps and levels.
            logging.basicConfig(level=log_level,
                                format="%(asctime)s - %(levelname)s - %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
        else:  # rawlog is True, so use a simple format without timestamps or levels.
            logging.basicConfig(level=log_level, format="%(message)s")

def configure_logging(basename: str, log_level: int | str = logging.INFO,
                      rawlog: bool = False, logdir: str | os.PathLike[str] = "") -> MemoryHandler | None:
    """
    Configure logging to write to files and stdout/stderr, and return a MemoryHandler to capture ERROR logs for later (duplicate) printing.

    Args:
        basename : Base name for the log files.
        log_level: Logging level (default: logging.INFO).
        rawlog   : If True, use a simple log format without timestamps or levels.
        logdir   : Directory to store log files. Defaults to './logs'.

    Returns:
        MemoryHandler instance capturing ERROR logs, or None if log files couldn't be created.

    Raises:
        None (file creation errors are caught and logged to stdout).
    """
    import datetime as dt

    root_logger = logging.getLogger()

    # Check if logging is already configured by checking for any handlers
    if root_logger.hasHandlers():
        for handler in root_logger.handlers:
            if isinstance(handler, MemoryHandler):
                return handler

    # Proceed with configuring logging if no MemoryHandler was found
    if not logdir:  # Default to the current working directory if no logdir is provided.
        logdir = Path.cwd().expanduser().resolve(strict=True) / "logs"
    else:
        logdir = ensure_path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now()
    log_base   = f".{basename}-log-{now.strftime('%Y%m%d-%H%M%S')}"
    log_info   = logdir / (log_base + ".out")
    log_errors = logdir / (log_base + ".err")

    root_logger.handlers = []  # Reset any existing handlers

    # File handlers for logging to files
    try:
        debug_info_handler    = logging.FileHandler(log_info)
        debug_info_handler.setLevel(logging.DEBUG)
        warning_error_handler = logging.FileHandler(log_errors)
        warning_error_handler.setLevel(logging.WARNING)
    except OSError as e:
        print(f"Failed to create log files: {e}", flush=True)
        return None

    # Stream handler for stdout (WARNING and lower)
    console_handler_stdout = FlushingStreamHandler(stream=sys.stdout)
    console_handler_stdout.setLevel(logging.DEBUG)  # Set to lowest level
    console_handler_stdout.addFilter(MaxLevelFilter(logging.WARNING))  # Highest

    # Stream handler for stderr (ERROR and above)
    console_handler_stderr = FlushingStreamHandler(stream=sys.stderr)
    console_handler_stderr.setLevel(logging.ERROR)  # Only logs ERROR and higher to stderr

    memory_handler = MemoryHandler(level=logging.ERROR)  # Only capture ERROR level logs

    # Define the formatter based on the no_prefix parameter
    if rawlog:
        log_format = logging.Formatter("%(message)s")
    else:
        log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    debug_info_handler.setFormatter(    log_format)
    warning_error_handler.setFormatter( log_format)
    console_handler_stdout.setFormatter(log_format)
    console_handler_stderr.setFormatter(log_format)
    memory_handler.setFormatter(        log_format)

    root_logger.setLevel(log_level)
    root_logger.addHandler(debug_info_handler)
    root_logger.addHandler(warning_error_handler)
    root_logger.addHandler(console_handler_stdout)
    root_logger.addHandler(console_handler_stderr)
    root_logger.addHandler(memory_handler)
    if not rawlog: root_logger.info("Logging to '%s' and '%s' with level %s", log_info, log_errors, logging.getLevelName(root_logger.level))

    return memory_handler

def print_all_errors(memory_handler: MemoryHandler,
                     rawlog: bool = False) -> None:
    """Print all the captured error messages."""
    if memory_handler.logs and not rawlog:
        print("\n******************************\n"
              "******************************\n"
              "All Error messages from above:")
        for log in memory_handler.logs:
            print(log)

def return_method_name(levels_up: int = 1) -> str:
    """
    Return the caller's qualified method/function name.

    - For instance methods: ClassName.method
    - For classmethods:     ClassName.method
    - For staticmethods:    ClassName.method on Python >= 3.11 (via co_qualname),
                            otherwise just 'method' (class is not recoverable without heuristics)
    - For functions:        function

    Args:
        levels_up: How many frames up to inspect (1 = caller). If greater than
                   the stack depth, the highest available frame is used.

    Returns:
        The current method name as a string, formatted as 'ClassName.method' or 'function'.

    Raises:
        None: This function does not raise exceptions, but it may log warnings
              if sys._getframe or inspect fails.
    """
    fallback_logging_config()
    try:
        levels = int(levels_up)
    except Exception as e:
        logging.warning("return_method_name(): levels_up argument is not an integer: %s", levels_up, exc_info=e)
        levels = 1
    if levels < 1:
        levels = 1
    name = "<unknown>"
    fr   = None
    # Try sys._getframe first
    try:
        fr = sys._getframe(levels)  # Get the frame at the specified level
    except Exception as e1:
        logging.warning("return_method_name(): sys._getframe(%s) failed. Falling back to inspect...", levels, exc_info=e1)
        try:
            import inspect
            frame = inspect.currentframe()
            try:
                fr = frame
                climbed = 0
                for _ in range(levels):
                    if fr is None or fr.f_back is None:
                        break
                    fr = fr.f_back
                    climbed += 1
                if climbed < levels:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("return_method_name(): truncated at top of stack (requested levels_up=%s but only climbed=%s)", levels, climbed)
            finally:
                if frame is not None:
                    try:
                        frame.clear()
                    except Exception as e:
                        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                            "Failed to clear frame: %s", e
                        )
                    del frame
        except Exception as e2:
            logging.warning("return_method_name(): inspect fallback failed", exc_info=e2)
            fr = None
    if fr is not None:
        # Python 3.11+: co_qualname gives 'Class.method' (or 'outer.<locals>.inner')
        qual = getattr(fr.f_code, "co_qualname", None)
        if isinstance(qual, str) and qual:
            # Remove all occurrences of '.<locals>.' from the qualified name.
            name = qual.replace(".<locals>.", ".")
        else:
            func     = fr.f_code.co_name
            self_obj = fr.f_locals.get("self")
            cls_obj  = fr.f_locals.get("cls")
            if self_obj is not None:
                name = f"{type(self_obj).__qualname__}.{func}"
            elif isinstance(cls_obj, type):
                name = f"{cls_obj.__qualname__}.{func}"
            else:
                argc = getattr(fr.f_code, "co_posonlyargcount", 0) + fr.f_code.co_argcount
                if argc:
                    for a in fr.f_code.co_varnames[:argc]:
                        obj = fr.f_locals.get(a)
                        if obj is not None:
                            t = obj if isinstance(obj, type) else type(obj)
                            attr = getattr(t, func, None)
                            if attr is not None:
                                name = f"{getattr(t, '__qualname__', t.__name__)}.{func}"
                                break
                    else:
                        name = func
                else:
                    name = func
    else:
        logging.warning("return_method_name(): no frame available.")
    if fr is not None:
        if name == "<module>":
            mod = fr.f_globals.get("__name__")
            if isinstance(mod, str) and mod:
                name = mod
    fr = None  # Clear the frame reference to free memory.
    return name
