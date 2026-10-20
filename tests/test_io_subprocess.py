"""`my_popen` against real child processes, and `my_fopen`'s encoding fallbacks."""

from __future__ import annotations

import codecs
import sys
import threading
from pathlib import Path

import pytest

from emmykit.extensions import TEXT_ENCODINGS, TEXT_ENCODINGS_SET
from emmykit.io_subprocess import MyPopenResult, my_fopen, my_popen


def _run_with_deadline(command: list[str], seconds: float) -> MyPopenResult | None:
    """Run `my_popen` in a daemon thread; return None if it hasn't finished in time."""
    results: list[MyPopenResult] = []
    worker = threading.Thread(
        target=lambda: results.append(my_popen(command, suppress_info=True)), daemon=True
    )
    worker.start()
    worker.join(seconds)
    return results[0] if results else None


def test_output_that_is_not_utf8_neither_hangs_nor_is_lost() -> None:
    """A byte that isn't valid text becomes U+FFFD; everything after it still arrives.

    Fails, by hanging, if the reader thread dies on the bad byte: nothing then
    drains the pipe, the child blocks once it fills, and `wait()` never returns.
    """
    child = (
        "import sys\n"
        "sys.stdout.buffer.write(b'\\xff\\n' + b'a' * 200_000 + b'\\n')\n"
        "sys.stderr.buffer.write(b'\\xfe\\n')\n"
    )

    result = _run_with_deadline([sys.executable, "-c", child], seconds=15)

    assert result is not None, "my_popen hung"
    assert result.returncode == 0
    assert result.stdout == "\ufffd\n" + "a" * 200_000 + "\n"
    assert result.stderr == "\ufffd\n"


# --- my_fopen: which encoding wins -------------------------------------------

def test_text_encodings_is_the_short_text_only_list() -> None:
    """UTF-8 (BOM-aware), UTF-16, CP1252, then latin-1 last; no non-text codecs."""
    assert TEXT_ENCODINGS == ("utf-8-sig", "utf-16", "cp1252", "latin-1")
    assert TEXT_ENCODINGS_SET == frozenset(TEXT_ENCODINGS)


HELLO = "héllo €\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (codecs.BOM_UTF8 + HELLO.encode("utf-8"), HELLO),
        (HELLO.encode("utf-8"), HELLO),
        (codecs.BOM_UTF16_LE + HELLO.encode("utf-16-le"), HELLO),
        (codecs.BOM_UTF16_BE + HELLO.encode("utf-16-be"), HELLO),
        # Even length and no BOM: it also decodes as (meaningless) UTF-16.
        ("naïve “café” — €5\n".encode("cp1252"), "naïve “café” — €5\n"),
        # 0x81 is undefined in CP1252, so only latin-1 can read it.
        (b"a\x81b\n", "a\x81b\n"),
    ],
    ids=["utf-8-bom", "utf-8", "utf-16-le-bom", "utf-16-be-bom", "cp1252", "latin-1"],
)
def test_my_fopen_picks_the_right_encoding(tmp_path: Path, raw: bytes, expected: str) -> None:
    """Each kind of file comes back as the text that was written, with any BOM removed."""
    path = tmp_path / "f.txt"
    path.write_bytes(raw)

    assert my_fopen(path, suppress_errors=True) == expected
