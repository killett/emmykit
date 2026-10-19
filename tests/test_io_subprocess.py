"""`my_popen` against real child processes."""

from __future__ import annotations

import sys
import threading

from emmykit.io_subprocess import MyPopenResult, my_popen


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
