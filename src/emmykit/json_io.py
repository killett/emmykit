"""json_io — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os

from enum import Enum
from pathlib import Path
from typing import Any

from emmykit.constants import DEFAULT_ENCODING
from emmykit.options import Options
from emmykit.safe_paths import ensure_file


def to_jsonable(obj: Any, *, roundtrip: bool = True) -> Any:
    """
    Convert arbitrary Python objects into JSON-serializable primitives.
    If roundtrip=True, non-JSON types are wrapped with a small type tag so they can be reconstructed.
    """
    return _to_jsonable(obj, roundtrip=roundtrip, _seen=set())

def _to_jsonable(obj: Any, *, roundtrip: bool, _seen: set[int]) -> Any:
    """
    Internal helper to convert arbitrary Python objects into JSON-serializable primitives.
    If roundtrip=True, non-JSON types are wrapped with a small type tag so they can be reconstructed.
    (Helper exists to avoid exposing the _seen set in the public API.)
    """
    # Fast-path primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # Dict
    if isinstance(obj, dict):
        oid = id(obj)
        if oid in _seen:
            return {"__type__": "recursion"}
        _seen.add(oid)
        try:
            return {str(k): _to_jsonable(v, roundtrip=roundtrip, _seen=_seen) for k, v in obj.items()}
        finally:
            _seen.discard(oid)
    # List
    if isinstance(obj, list):
        oid = id(obj)
        if oid in _seen:
            return {"__type__": "recursion"}
        _seen.add(oid)
        try:
            return [_to_jsonable(x, roundtrip=roundtrip, _seen=_seen) for x in obj]
        finally:
            _seen.discard(oid)
    # Tuple
    if isinstance(obj, tuple):
        oid = id(obj)
        if oid in _seen:
            return {"__type__": "recursion"}
        _seen.add(oid)
        try:
            seq = [_to_jsonable(x, roundtrip=roundtrip, _seen=_seen) for x in obj]
        finally:
            _seen.discard(oid)
        return {"__type__": "tuple", "value": seq} if roundtrip else list(seq)
    # Set / Frozenset
    if isinstance(obj, (set, frozenset)):
        oid = id(obj)
        if oid in _seen:
            return {"__type__": "recursion"}
        _seen.add(oid)
        try:
            seq = [_to_jsonable(x, roundtrip=roundtrip, _seen=_seen) for x in obj]
        finally:
            _seen.discard(oid)
        tag = "frozenset" if isinstance(obj, frozenset) else "set"
        return {"__type__": tag, "value": seq} if roundtrip else list(seq)
    # Path
    if isinstance(obj, Path):
        s = obj.as_posix()
        return {"__type__": "path", "value": s} if roundtrip else s
    # Enum
    if isinstance(obj, Enum):
        # Store module+qualname so we *can* reconstruct if the Enum is importable.
        cls = obj.__class__
        return {
            "__type__" : "enum",
            "module"   : cls.__module__,
            "qualname" : getattr(cls, "__qualname__", cls.__name__),
            "name"     : obj.name,
        } if roundtrip else (obj.value if isinstance(obj.value, (str, int, float, bool, type(None))) else obj.name)
    # argparse.Namespace
    try:
        import argparse
        if isinstance(obj, argparse.Namespace):
            return {"__type__" : "namespace",
                    "value"    : _to_jsonable(vars(obj), roundtrip=roundtrip, _seen=_seen)} if roundtrip else vars(obj)
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Failed to unwrap argparse.Namespace: %s", e
        )
    # datetime / date / time
    try:
        import datetime as dt
        if isinstance(obj, (dt.datetime, dt.date, dt.time)):
            iso = obj.isoformat()
            which = "datetime" if isinstance(obj, dt.datetime) else ("date" if isinstance(obj, dt.date) else "time")
            return {"__type__": which, "value": iso} if roundtrip else iso
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Failed to unwrap datetime/date/time: %s", e
        )
    # Decimal
    try:
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return {"__type__": "decimal", "value": str(obj)} if roundtrip else float(obj)
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Failed to unwrap decimal.Decimal: %s", e
        )
    # bytes-like
    if isinstance(obj, (bytes, bytearray, memoryview)):
        try:
            import base64
            b64  = base64.b64encode(bytes(obj)).decode("ascii")
            kind = "bytes" if isinstance(obj, bytes) else ("bytearray" if isinstance(obj, bytearray) else "memoryview")
            return {"__type__": kind, "value": b64} if roundtrip else b64
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to unwrap bytes/bytearray/memoryview: %s", e
            )
            return str(obj)
    # re.Pattern (compiled regex)
    try:
        import re
        if isinstance(obj, re.Pattern):
            return {"__type__": "re_pattern", "pattern": obj.pattern, "flags": obj.flags} if roundtrip else obj.pattern
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Failed to unwrap re.Pattern: %s", e
        )
    # Fallback
    stringified = str(obj)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Object of type %s is not JSON serializable; converting to string: %s", type(obj).__name__, stringified)
    return stringified if not roundtrip else {"__type__": "object", "value": stringified}

def from_jsonable(obj: Any) -> Any:
    """
    Reconstruct objects encoded with to_jsonable(..., roundtrip=True).
    If input was produced with roundtrip=False, this mostly passes values through.
    """
    # Lists first
    if isinstance(obj, list):
        return [from_jsonable(x) for x in obj]
    # Primitives / not dict
    if not isinstance(obj, dict):
        return obj

    t = obj.get("__type__")
    if not t:
        return {k: from_jsonable(v) for k, v in obj.items()}

    # Known tags
    if t == "path":
        return Path(obj["value"])
    if t == "tuple":
        return     tuple(from_jsonable(x) for x in obj.get("value", []))
    if t == "set":
        return       set(from_jsonable(x) for x in obj.get("value", []))
    if t == "frozenset":
        return frozenset(from_jsonable(x) for x in obj.get("value", []))
    if t == "namespace":
        try:
            import argparse
            return argparse.Namespace(**from_jsonable(obj.get("value", {})))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to reconstruct argparse.Namespace: %s", e
            )
            return from_jsonable(obj.get("value", {}))
    if t == "enum":
        # Best effort: import the Enum class and get member by name; else return the name.
        try:
            import importlib
            mod   = importlib.import_module(obj["module"])
            parts = obj["qualname"].split(".")
            cls   = mod
            for p in parts:
                cls = getattr(cls, p)
            return getattr(cls, obj["name"])
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to reconstruct enum: %s", e
            )
            return obj.get("name")
    if t == "datetime":
        import datetime as dt
        return dt.datetime.fromisoformat(obj.get("value", ""))
    if t == "date":
        import datetime as dt
        return     dt.date.fromisoformat(obj.get("value", ""))
    if t == "time":
        import datetime as dt
        return     dt.time.fromisoformat(obj.get("value", ""))
    if t == "decimal":
        try:
            from decimal import Decimal
            return Decimal(obj.get("value", "0"))
        except Exception:
            return obj.get("value")
    if t == "bytes":
        try:
            import base64
            return            base64.b64decode(obj.get("value", "").encode("ascii"))
        except Exception:
            return obj.get("value")
    if t == "bytearray":
        try:
            import base64
            return  bytearray(base64.b64decode(obj.get("value", "").encode("ascii")))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to unwrap bytearray: %s", e
            )
            return obj.get("value")
    if t == "memoryview":
        try:
            import base64
            return memoryview(base64.b64decode(obj.get("value", "").encode("ascii")))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to unwrap memoryview: %s", e
            )
            return obj.get("value")
    if t == "recursion":
        return "<recursion>"
    if t == "object":
        return obj.get("value")
    if t == "re_pattern":
        import re
        return re.compile(obj.get("pattern", ""), obj.get("flags", 0))
    # Unknown tag → decode inner content if any
    return {k: from_jsonable(v) for k, v in obj.items()}

def _coerce_log_mode(value: Any) -> int:
    """Accept old string values like 'INFO' (or '20') and return an int."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        # Handle numeric strings like "20"
        try:
            return int(s)
        except ValueError as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "Failed to coerce log mode from string: %s", e
            )
        # Handle level names like "INFO", "debug", etc. (case-insensitive)
        value_map = {"INFO"     : logging.INFO,
                     "DEBUG"    : logging.DEBUG,
                     "WARNING"  : logging.WARNING,
                     "WARN"     : logging.WARNING,
                     "ERROR"    : logging.ERROR,
                     "CRITICAL" : logging.CRITICAL}
        lvl = value_map.get(s.upper())
        # lvl = logging.getLevelName(s.upper())  # deprecated
        if isinstance(lvl, int):
            return lvl
    logging.warning("Unrecognized log_mode %r; defaulting to INFO", value)
    return logging.INFO

def save_options_to_json(options: Options) -> None:
    """
    Save the options object to a JSON file.

    Args:
        options: Options object containing:
            - script_dir:    Directory where the JSON file will be saved.
            - python_script: Name of the Python script (used in the JSON filename).
            - my_name:       Name of the current script (used in the JSON filename).
            - timestamp:     Current timestamp (used in the JSON filename).

    Returns:
        None - writes the options to a JSON file.

    Raises:
        IOError:    If there is an error writing to the file.
        ValueError: If the options object is invalid.
    """
    import json
    options.options_json_filepath = options.script_dir / f".{options.python_script.name}-{options.my_name}-last-used-on-{options.timestamp}.json"
    options.options_json_filepath.parent.mkdir(parents=True, exist_ok=True)

    options_dict = options.__dict__.copy()  # Convert options to a dictionary and handle sets
    payload      = to_jsonable(options_dict, roundtrip=True)  # tag for safe round-trip

    # Write the dictionary to a JSON file (ensure_ascii=False to preserve non-ASCII characters)
    with open(options.options_json_filepath, "w", encoding=DEFAULT_ENCODING) as json_file:
        json.dump(payload, json_file, indent=4, ensure_ascii=False)

    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Options saved to JSON file: %s",
                                                                      os.fspath(options.options_json_filepath))

def load_options_from_json(options: Options, json_file: str | os.PathLike[str]) -> Options | None:
    """
    Load the options object from a JSON file.

    Args:
        options:    An existing Options object (used for logging purposes).
        json_file:  Path to the JSON file to load.

    Returns:
        Options object loaded from the JSON file, or None if the file does not exist or cannot be read.

    Raises:
        IOError:    If there is an error reading the file.
        ValueError: If the JSON file is invalid or cannot be parsed.
    """
    import json
    import copy
    json_file = ensure_file(json_file)
    with open(json_file, "r", encoding=DEFAULT_ENCODING) as file:
        raw = json.load(file)

    options_dict = from_jsonable(raw)  # reconstruct tagged types

    # Backwards compatibility: coerce old string log levels to ints
    if "log_mode" in options_dict:
        options_dict["log_mode"] = _coerce_log_mode(options_dict["log_mode"])

    # Create a new Options object and set attributes from the dictionary
    options_FROM_JSON = copy.deepcopy(Options())  # Just in case.
    for key, value in options_dict.items():
        setattr(options_FROM_JSON, key, value)
    if not options.rawlog: logging.info("options loaded from %s", os.fspath(json_file))
    return options_FROM_JSON
