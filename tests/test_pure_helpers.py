"""Byte-compare pure-helper outputs against the pre-split baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import emmykit

BASELINE = json.loads(
    (Path(__file__).parent / "_baseline_pure_helpers.json").read_text()
)


def _flatten() -> list[tuple[str, list, dict]]:
    """Return (name, args, entry_dict) for every recorded baseline call."""
    rows = []
    for name, entries in BASELINE.items():
        for entry in entries:
            rows.append((name, entry["args"], entry))
    return rows


@pytest.mark.parametrize(
    "name,args,entry",
    _flatten(),
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_pure_helper_output_matches_baseline(
    name: str, args: list, entry: dict
) -> None:
    """For each baseline call, the post-split helper must produce the same repr/exception."""
    fn = getattr(emmykit, name)
    if "result" in entry:
        actual = fn(*args)
        assert repr(actual) == entry["result"], (
            f"{name}({args!r}) drift: baseline={entry['result']!r} "
            f"actual={actual!r}"
        )
    else:
        expected_err = entry["error"]
        with pytest.raises(Exception) as exc_info:
            fn(*args)
        actual_err = f"{type(exc_info.value).__name__}: {exc_info.value}"
        assert actual_err == expected_err, (
            f"{name}({args!r}) error drift: baseline={expected_err!r} "
            f"actual={actual_err!r}"
        )
