"""Pin the public surface to the checked-in baseline, exactly."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import pkgutil
import re
import subprocess
import sys
from pathlib import Path

import emmykit

BASELINE = json.loads(
    (Path(__file__).parent / "_baseline_signatures.json").read_text()
)

PUBLIC_NAMES = sorted(n for n in dir(emmykit) if not n.startswith("_"))

# Object-repr memory addresses (e.g. dataclasses._MISSING_TYPE sentinels in
# `field()`'s default) vary across processes; normalize them before comparing.
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")


def _normalize_sig(sig: str, home: Path | None = None) -> str:
    """Strip what varies between machines and processes from a signature string.

    Memory addresses become ``0xADDR``. The home directory, which
    `LLMConfig`'s default database path is built from, becomes ``~``.

    Args:
        sig: A signature as ``str(inspect.signature(obj))`` gives it.
        home: The home directory the signature was computed under; defaults
            to this process's.

    Returns:
        The signature with both replaced.
    """
    sig = sig.replace(str((home or Path.home()).resolve()), "~")
    return _ADDR_RE.sub("0xADDR", sig)


def test_public_name_set_matches_baseline() -> None:
    """Public names must match the baseline exactly: nothing missing, nothing extra.

    The baseline is maintained deliberately, curated on its own merits — it
    is no longer derived from the legacy `univ_defs` surface.
    """
    expected = set(BASELINE)
    current = set(PUBLIC_NAMES)
    missing = expected - current
    extra = current - expected
    assert not missing, f"missing public symbols: {sorted(missing)}"
    assert not extra, f"extra public symbols: {sorted(extra)}"


def test_all_matches_baseline() -> None:
    """`__all__` lists exactly the baseline names, once each.

    `dir(emmykit)` also shows names that are imported but left out of
    `__all__`; `import *` and the README generator go by `__all__`.
    """
    assert sorted(emmykit.__all__) == sorted(BASELINE)


def test_every_public_name_keeps_its_kind() -> None:
    """Each name is still the same kind of object, e.g. a tuple constant hasn't become a list."""
    changed = {
        name: (entry["kind"], type(getattr(emmykit, name)).__name__)
        for name, entry in BASELINE.items()
        if type(getattr(emmykit, name)).__name__ != entry["kind"]
    }
    assert changed == {}


def test_callable_signatures_match_baseline() -> None:
    """Every callable symbol's str(signature) must equal the baseline string."""
    for name, entry in BASELINE.items():
        baseline_sig = entry.get("signature")
        if baseline_sig is None:
            continue  # baseline couldn't introspect (built-in, special) -> skip
        obj = getattr(emmykit, name)
        actual_sig = str(inspect.signature(obj))
        assert _normalize_sig(actual_sig) == _normalize_sig(baseline_sig), (
            f"signature drift for {name!r}: baseline={baseline_sig!r} "
            f"actual={actual_sig!r}"
        )


def test_signatures_match_baseline_under_another_home(tmp_path: Path) -> None:
    """The baseline names no machine's home directory, so the check passes anywhere.

    `LLMConfig`'s default database path is built from the home directory when
    emmykit is imported, so this imports it afresh with HOME pointing elsewhere.
    """
    names = [n for n, entry in BASELINE.items() if entry.get("signature") is not None]
    script = (
        "import inspect, json, sys, emmykit\n"
        "names = json.loads(sys.stdin.read())\n"
        "print(json.dumps({n: str(inspect.signature(getattr(emmykit, n))) for n in names}))\n"
    )
    src = Path(emmykit.__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(names), capture_output=True, text=True, check=True,
        env={**os.environ, "HOME": str(tmp_path), "PYTHONPATH": str(src)},
    )
    actual = json.loads(result.stdout)
    drift = {
        n: actual[n] for n in names
        if _normalize_sig(actual[n], home=tmp_path)
        != _normalize_sig(BASELINE[n]["signature"], home=tmp_path)
    }
    assert drift == {}


def test_every_submodule_imports() -> None:
    """Every submodule under emmykit/ must import without error."""
    pkg_dir = Path(emmykit.__file__).parent
    submodules = sorted(
        info.name
        for info in pkgutil.iter_modules([str(pkg_dir)])
        if not info.name.startswith("_") or info.name == "_version"
    )
    failed = []
    for sub in submodules:
        try:
            importlib.import_module(f"emmykit.{sub}")
        except Exception as exc:
            failed.append(f"{sub}: {type(exc).__name__}: {exc}")
    assert not failed, "submodule import failures:\n" + "\n".join(failed)


def test_options_has_no_shell_alias_fields() -> None:
    """The shell/alias installer state was removed in 0.5.0."""
    options = emmykit.Options()
    removed = ["shell", "rc_file", "alias", "alias_command",
               "additional_alias_files"]
    present = [name for name in removed if hasattr(options, name)]
    assert not present, f"removed Options fields still present: {present}"


def test_no_stdlib_reexports() -> None:
    """The stdlib re-exports were removed from the public surface in 0.5.0."""
    removed = [
        "Any", "Callable", "Enum", "Final", "Iterable", "Literal", "Path",
        "Protocol", "Sequence", "TextIO", "ThreadPoolExecutor", "Type",
        "TypeAlias", "annotations", "chain", "dataclass", "errno", "field",
        "logging", "os", "overload", "re", "replace", "sys",
    ]
    present = [name for name in removed if hasattr(emmykit, name)]
    assert not present, f"stdlib re-exports still on the surface: {present}"
