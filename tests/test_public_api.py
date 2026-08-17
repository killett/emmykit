"""Pin the post-split public surface to the pre-split baseline."""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path

import emmykit

BASELINE = json.loads(
    (Path(__file__).parent / "_baseline_signatures.json").read_text()
)

PUBLIC_NAMES = sorted(n for n in dir(emmykit) if not n.startswith("_"))

# Object-repr memory addresses (e.g. dataclasses._MISSING_TYPE sentinels in
# `field()`'s default) vary across processes; normalize them before comparing.
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")


def _normalize_sig(sig: str) -> str:
    """Strip non-reproducible memory addresses from a signature string."""
    return _ADDR_RE.sub("0xADDR", sig)


def test_public_name_set_matches_baseline() -> None:
    """Every non-_ symbol in the legacy univ_defs surface must be re-exported."""
    expected = set(BASELINE)
    current = set(PUBLIC_NAMES)
    missing = expected - current
    extra = current - expected
    assert not missing, f"missing public symbols: {sorted(missing)}"
    assert not extra, f"extra public symbols: {sorted(extra)}"


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
