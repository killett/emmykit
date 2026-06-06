"""introspection — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import re
import sys

from collections.abc import Callable
from typing import Any, TextIO, Type

from emmykit.constants import DEFAULT_ENCODING
from emmykit.logging_utils import fallback_logging_config, return_method_name
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import ensure_file, safe_exists, safe_is_dir, safe_is_file
from emmykit.io_subprocess import my_fopen


def load_ast_var(var_name: str, script_path: str | os.PathLike[str],
                 rawlog: bool = False) -> Any | None:
    """
    Load a top-level literal Python variable from a module without executing it.

    Args:
        var_name:    The name of the global variable to extract from the script.
        script_path: The path to the Python script file from which to extract the variable.
        rawlog:      If True, use a simple log format without timestamps or levels.

    Returns:
        The value of the variable if found, or None.

    Raises:
        FileNotFoundError: If the script file does not exist.
        AttributeError:    If the variable is not found at the top level of the script.
        ValueError:        If the value of the variable cannot be evaluated as a literal expression.
    """
    import ast
    fallback_logging_config(rawlog=rawlog)
    script_path  = ensure_file(script_path)
    file_content = my_fopen(script_path, rawlog=rawlog)
    if not file_content:
        raise FileNotFoundError(f"Failed to open {os.fspath(script_path)}")
    tree = ast.parse(file_content, script_path)
    if tree is None:
        raise SyntaxError(f"Could not parse {os.fspath(script_path)}")

    for node in tree.body:
        # handle plain assignments: var_name = <expr>
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError as e:
                        raise ValueError(f"Cannot literal_eval the value of {var_name}: {e}") from e
        # also handle annotated assignments: var_name: Type = <expr>
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == var_name and node.value:
                try:
                    return ast.literal_eval(node.value)
                except ValueError as e:
                    raise ValueError(f"Cannot literal_eval the value of {var_name}: {e}") from e

    logging.info("Top-level variable %r not found in %s", var_name, os.fspath(script_path))
    return None

def _sanitize_text_signature(sig: str | None) -> str:
    """
    Clean up a __text_signature__ string for display.

    Args:
        sig: The __text_signature__ string to clean up.

    Returns:
        A cleaned-up version of the signature string.

    Raises:
        None.
    """
    if not sig:
        return "(...)"
    s = sig
    # Replace CPython-internal placeholders
    s = s.replace("$self", "self").replace("$module", "")
    # Tidy up commas/spaces that might be left after removing $module
    s = re.sub(r"\(\s*,", "(", s)
    s = re.sub(r",\s*,", ", ", s)
    s = s.replace("(,", "(").replace(", )", ")")
    return s

def _builtin_stub(obj: object) -> str:
    """
    Return a stub definition for a built-in or C-extension function.

    Args:
        obj: The built-in function or method object.

    Returns:
        A string representing a stub definition of the function.

    Raises:
        None.
    """
    import inspect
    from textwrap import indent
    def_name = getattr(obj, "__name__", getattr(obj, "__qualname__", "<builtin>"))
    context = None
    if hasattr(obj, "__objclass__"):
        context = f"{obj.__objclass__.__name__}.{def_name}"   # e.g., "list.append"
    else:
        mod = getattr(obj, "__module__", None)
        if mod and mod != "builtins":
            context = f"{mod}.{def_name}"                     # e.g., "math.prod"
    header = f"# {context}\n" if context else ""

    try:
        # Tell inspect.signature that obj is callable to appease mypy
        from typing import cast, Callable as TypingCallable
        sig = str(inspect.signature(cast(TypingCallable[..., Any], obj)))
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "_builtin_stub: inspect.signature failed for %s: %s", def_name, e
        )
        sig = _sanitize_text_signature(getattr(obj, "__text_signature__", None))

    doc = inspect.getdoc(obj) or "Built-in function; Python source unavailable."
    doc = doc.replace('"""', '\\"""')  # keep our triple quotes intact
    doc = indent(doc, "    ")
    return f"{header}def {def_name}{sig}:\n    \"\"\"\n{doc}\n    \"\"\"\n    ...\n"

def show_function_source(target: object | str, *, unwrap: bool = True,
                         output: str | os.PathLike[str] | TextIO | None = None) -> str:
    """
    Print the full source text of a Python function (including comments,
    docstrings, decorators, and type hints).

    Args:
        target: A function *name* (string) or a function object.
                If a string is given, it's resolved in the caller's scope, then
                in builtins, then as a dotted path via pydoc.locate (e.g. 'pkg.mod.func').
        unwrap: If True, attempt to unwrap decorated functions to show
                the original implementation. Defaults to True.
        output: A file-like object to write to (optional, defaults to sys.stdout). More details:

    Details on the "output" argument:
    - None -> sys.stdout
    - TextIO (e.g., sys.stdout, an open text file, StringIO) -> used as-is
             (must be opened in *text* mode; binary streams are rejected)
    - str | os.PathLike[str] -> treated as a path:
             * '~' is expanded
             * parent directories are created (parents=True, exist_ok=True)
             * file is opened in append mode ('a', UTF-8)
             * a one-line note is written indicating whether we created or appended
    Notes:
    - A trailing newline is added if the source text doesn't already end with one.
    - If you pass the string "-" as the output path, it is treated as stdout.
    - If the given path is an existing directory, an IsADirectoryError is raised.
    - If you pass a binary stream, a TypeError is raised.

    Returns:
        str: The source text that was printed.

    Raises:
        NameError: If a string cannot be resolved to an object.
        OSError:   If source is unavailable (e.g., built-in/C extension or optimized away).
        TypeError: If the resolved object isn't suitable for source extraction.
    """
    import builtins
    import functools
    import inspect
    import pydoc
    import io
    from types  import FrameType
    from typing import cast, Callable as TypingCallable
    # Resolve the object if 'target' is a string
    if isinstance(target, str):
        name  = target
        currentframe = inspect.currentframe()
        assert currentframe is not None
        theframe = currentframe.f_back  # caller's frame
        assert theframe is not None
        frame: FrameType = theframe     # help mypy narrow for f_locals / f_globals
        try:
            obj = frame.f_locals.get(name)
            if obj is None:
                obj = frame.f_globals.get(name)
            if obj is None:
                obj = getattr(builtins, name, None)
            if obj is None and "." in name:
                head, *tail = name.split(".")
                base = frame.f_locals.get(head)
                if base is None:
                    base = frame.f_globals.get(head)
                if base is None:
                    base = getattr(builtins, head, None)
                if base is not None:
                    try:
                        for part in tail:
                            base = getattr(base, part)
                        obj = base
                    except Exception as e:
                        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                            "Failed to resolve %s: %s", part, e
                        )
            if obj is None:
                # Try dotted-path resolution (e.g., "pkg.module.func")
                obj = pydoc.locate(name)
        finally:
            # Avoid reference cycles
            del frame

        if obj is None:
            raise NameError(f"Could not resolve '{name}' to a function object.")
    else:
        obj = target

    # Optionally unwrap decorated functions
    if unwrap:
        try:
            # Tell inspect.signature that obj is callable to appease mypy
            obj = inspect.unwrap(cast(TypingCallable[..., Any], obj))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "%s: Failed to unwrap %s: %s", return_method_name(), obj, e
            )

    if isinstance(obj, functools.partial):
        obj = obj.func

    if not (inspect.isroutine(obj) or inspect.ismethoddescriptor(obj)):
        if callable(obj):        # use callable(), not getattr/hasattr
            call = obj.__call__  # bound method; safe after callable()
            if inspect.isfunction(call) or inspect.ismethod(call):
                obj = call

    # Built-ins / C-extensions don't have retrievable Python source
    if inspect.isbuiltin(obj) or inspect.ismethoddescriptor(obj):
        src = _builtin_stub(obj)
    else:  # Tell inspect.signature that obj is callable to appease mypy
        src = inspect.getsource(cast(TypingCallable[..., Any], obj))

    # Decide where to write
    out:                       TextIO
    closer: Callable[[], None] | None = None  # callable to close if *we* open a file
    note:                  str | None = None
    if output is None:
        out = sys.stdout
    # Accept known text-mode IO bases directly
    elif isinstance(output, (io.TextIOBase, io.StringIO)):
        out = cast(TextIO, output)  # Tell mypy that "out" has type TextIO
    # Accept "-" as a common alias for stdout
    elif isinstance(output, (str, os.PathLike)) and str(output) == "-":
        out = sys.stdout
    # Path-like or string path
    elif isinstance(output, (str, os.PathLike)):
        path = ensure_path(output).resolve()
        if safe_is_dir(path):
            raise IsADirectoryError(f"Output path is a directory: {os.fspath(path)}")
        # Ensure parents exist ('.' is fine to call mkdir() on with exist_ok=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = safe_exists(path)
        note = (f"# Appending to existing file: {os.fspath(path)}"
                if exists
                else f"# Creating new file: {os.fspath(path)}")
        # Try atomic write helper if available; fall back on any failure.
        _maw = globals().get("my_atomic_write")
        if callable(_maw):
            try:
                # newline hygiene: one newline after note; ensure src ends with exactly one
                payload = (note + "\n") + (src if src.endswith("\n") else src + "\n")
                _maw(path, payload, "a", encoding=DEFAULT_ENCODING)
                return src
            except Exception as e:
                # Non-atomic fallback below
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                    "my_atomic_write failed for %s: %s", path, e
                )
        # newline="" lets print() manage newlines consistently across platforms
        out = path.open("a", encoding=DEFAULT_ENCODING, newline="")
        closer = out.close
    # Last chance: duck-typed "file-like" with a text write() method.
    # Reject binary streams explicitly.
    elif hasattr(output, "write"):
        if isinstance(output, (io.BufferedIOBase, io.RawIOBase)):
            raise TypeError("Binary streams are not supported; provide a text-mode stream.")
        out = output  # type: ignore[assignment]
    else:
        raise TypeError("output must be None, a path (str/os.PathLike), or a text-mode TextIO.")
    try:
        if note:
            print(note, file=out)
        print(src, file=out, end="" if src.endswith("\n") else "\n")
    finally:
        if closer is not None:
            closer()
    return src

def normalize_to_dict(value: Any, var_name: str, script_path: str | os.PathLike[str]) -> dict:
    """Ensure that 'value' is a dict. If it's a JSON-style string, try to parse it. Otherwise, log a warning and return an empty dict."""
    import json
    fallback_logging_config()
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    script_path_str = os.fspath(script_path)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            logging.warning("Variable %r in %r JSON-decoded to %s, expected dict.", var_name, script_path_str, type(parsed).__name__)
        except json.JSONDecodeError as e:
            logging.warning("Failed to JSON-decode variable %r from %s. Expected a dict or JSON string.", var_name, script_path_str, exc_info=e)
    else:
        logging.warning("Variable %r in %s is of type %s, expected dict or JSON string.", var_name, script_path_str, type(value).__name__)
    return {}

def if_filepath_then_read(input_string_or_filepath: str | os.PathLike[str],
                          force_string: bool = False) -> str:
    """
    If given a path, return the file's text; otherwise return the string itself.

    Behavior:
    - If a real PathLike is passed and 'force_string' is False:
        * If the path does not exist → raise FileNotFoundError.
        * If the path exists but is not a regular file → raise IsADirectoryError.
        * If it is a file → return its contents. On permission or decoding errors,
          log and return "".
        * A race after the existence check may still raise FileNotFoundError (re-raised).
    - If a string is passed:
        * If it contains a newline or is longer than 4096 chars → treat as literal and return as-is.
        * Else, if it names an existing file and 'force_string' is False → read and return
          contents; on read errors (not found/permission/decoding), log and return "".
        * Else → return the string as-is.
    - If 'force_string' is True and a PathLike is passed → TypeError.

    Args:
        input_string_or_filepath: A string to return as-is, or a path to read.
        force_string:             If True, always treat the input as a string literal (PathLike
                                  inputs are rejected with TypeError).

    Returns:
        The file contents (when reading a file) or the input string/literal path.

    Raises:
        TypeError:         If a PathLike is given with 'force_string=True', or if the input
                           is neither str nor PathLike.
        FileNotFoundError: When a PathLike is given and the path does not exist.
        IsADirectoryError: When a PathLike is given and the path is not a regular file.

    Notes:
        For string inputs that look like paths, missing files do not raise; the
        string is returned unchanged. Permission/decoding errors are logged and
        result in an empty string.
    """
    fallback_logging_config()

    # If a real PathLike was passed, handle it explicitly (different semantics than str)
    if isinstance(input_string_or_filepath, os.PathLike):
        if force_string:
            raise TypeError("'input_string_or_filepath' was given as a file path "
                            f"({input_string_or_filepath!r}) but 'force_string' is True.")
        file_path = ensure_path(input_string_or_filepath)

        # Raise if it doesn't exist (your new requirement)
        if not safe_exists(file_path):
            raise FileNotFoundError(os.fspath(file_path))

        # Exists but not a regular file → raise
        if not safe_is_file(file_path):
            raise IsADirectoryError(os.fspath(file_path))

        # Read the file
        try:
            contents = my_fopen(file_path, suppress_errors=True)
            if not contents:
                logging.error("Could not read file: %s", os.fspath(file_path))
                return ""
            return contents
        except FileNotFoundError:
            # Unlikely now (we checked), but keep for races
            logging.exception("File not found: %s", os.fspath(file_path))
            raise
        except PermissionError:
            logging.exception("Permission denied: %s", os.fspath(file_path))
            return ""
        except UnicodeDecodeError:
            logging.exception("Could not decode %r.", os.fspath(file_path))
            return ""

    # From here: input is a str (or we already returned/raised above)

    # Heuristics: if it contains newlines or is ridiculously long, it's source.
    if isinstance(input_string_or_filepath, str) and (
        "\n" in input_string_or_filepath or len(input_string_or_filepath) > 4096
    ):
        return input_string_or_filepath

    # If it's a string that points to an existing file (and not forced-string), read it
    if not force_string and safe_is_file(file_path := ensure_path(input_string_or_filepath)):
        try:
            contents = my_fopen(file_path, suppress_errors=True)
            if not contents:
                logging.error("Could not read file: %s", os.fspath(file_path))
                return ""
            return contents
        except FileNotFoundError:
            logging.exception("File not found: %s", os.fspath(file_path))
            return ""
        except PermissionError:
            logging.exception("Permission denied: %s", os.fspath(file_path))
            return ""
        except UnicodeDecodeError:
            logging.exception("Could not decode %r.", os.fspath(file_path))
            return ""

    # Otherwise treat it as a literal string
    if not isinstance(input_string_or_filepath, str):
        # (If we got here with a non-PathLike, non-str, it's a type error)
        raise TypeError("Expected 'input_string_or_filepath' to be a string or file path, "
                        f"got {type(input_string_or_filepath).__name__!r}")
    return input_string_or_filepath

def compile_code(source_or_filepath: str | os.PathLike[str],
                 force_source: bool = False) -> bool:
    """
    Attempt to compile the given source code in 'exec' mode.
    If 'source_or_filepath' is a file path, read its contents first.

    Args:
        source_or_filepath: The source code string or file path to compile.
        force_source:       If True, treat 'source_or_filepath' as a source code string even if it looks like a file path.

    Returns:
        True if compilation succeeds, False if it fails with a SyntaxError or other exception

    Raises:
        SyntaxError: If the source code has a syntax error, it will be logged and False is returned.
        TypeError:   If 'source_or_filepath' is not a string or a file path.
    """
    fallback_logging_config()
    # Read from file if source is a file path
    source = if_filepath_then_read(source_or_filepath, force_string=force_source)
    file_path: str | os.PathLike[str] = ""
    if source != source_or_filepath:
        file_path = ensure_path(source_or_filepath)
    else:
        # If it's a string, we need to provide a dummy file path for the compiler.
        # This is just to satisfy the compiler, it won't be used.
        file_path = "<string>"
    try:
        compile(source, file_path, "exec")
    except SyntaxError as e:
        # protect against None offsets
        lineno  = e.lineno or "?"
        offset  = e.offset or 0
        line    = (e.text or "").rstrip("\n")
        pointer = " " * (offset - 1) + "^" if offset else ""
        logging.error(f"Syntax error in {e.filename!r}, line {lineno}, column {offset}:\n"
                      f"    {line}\n"
                      f"    {pointer}\n"
                      f"    {e.msg!r}", exc_info=True)
        return False
    return True
