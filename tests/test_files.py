"""`download_file`, with the network, free-space query and sleep faked."""

from __future__ import annotations

import errno
import io
import os
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError

import pytest

from emmykit import files

URL = "https://example.invalid/data.bin"


class _Response:
    """A minimal `urlopen` response: a context manager with headers and read()."""

    def __init__(self, body: bytes, length: int | None) -> None:
        """Serve `body`, advertising `length` as Content-Length when it isn't None."""
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self._body = io.BytesIO(body)

    def read(self, n: int) -> bytes:
        """Return up to `n` bytes of the body."""
        return self._body.read(n)

    def __enter__(self) -> _Response:
        """Return the response itself."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Nothing to close."""


@pytest.fixture
def requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record each request's method; sleeps return at once and are recorded as "sleep <s>"."""
    log: list[str] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: log.append(f"sleep {seconds}"))
    return log


def _serve(monkeypatch: pytest.MonkeyPatch, log: list[str],
           head: Callable[[], _Response], get: Callable[[int], _Response]) -> None:
    """Answer HEAD with `head()` and the n-th GET (from 1) with `get(n)`, logging each method."""
    gets = [0]

    def urlopen(req: urllib.request.Request, timeout: float) -> _Response:
        method = req.get_method()
        log.append(method)
        if method == "HEAD":
            return head()
        gets[0] += 1
        return get(gets[0])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def _no_head() -> _Response:
    """A HEAD request that fails, so no size is known up front."""
    raise URLError("HEAD not allowed")


def _no_get(n: int) -> _Response:
    """A GET that must not happen."""
    raise AssertionError("download_file sent a GET it should not have")


def test_too_little_space_for_the_advertised_size_raises_enospc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """A HEAD size larger than the free space is OSError(ENOSPC) before any GET, not SystemExit."""
    dest = tmp_path / "data.bin"
    _serve(monkeypatch, requests, head=lambda: _Response(b"", 5000), get=_no_get)
    monkeypatch.setattr(files, "query_free_space", lambda path: 10)

    with pytest.raises(OSError) as excinfo:
        files.download_file(URL, dest)

    assert excinfo.value.errno == errno.ENOSPC
    assert excinfo.value.strerror.startswith("Not enough disk space: need ")
    assert excinfo.value.filename == os.fspath(dest)
    assert requests == ["HEAD"]
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_too_little_space_for_the_served_size_raises_without_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """A GET size larger than the free space is OSError(ENOSPC) after one GET, with no retry.

    Fails if the error is an OSError that the retry handler catches, which
    would retry five times and sleep between attempts.
    """
    dest = tmp_path / "data.bin"
    _serve(monkeypatch, requests, head=_no_head, get=lambda n: _Response(b"x" * 5000, 5000))
    monkeypatch.setattr(files, "query_free_space", lambda path: 10)

    with pytest.raises(OSError) as excinfo:
        files.download_file(URL, dest)

    assert excinfo.value.errno == errno.ENOSPC
    assert requests == ["HEAD", "GET"]
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_failure_after_every_retry_raises_with_the_last_error_as_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """When every attempt fails, OSError names the URL and the attempt count and chains the last error."""
    def refuse(n: int) -> _Response:
        raise URLError(f"refused {n}")

    _serve(monkeypatch, requests, head=_no_head, get=refuse)

    with pytest.raises(OSError) as excinfo:
        files.download_file(URL, tmp_path / "data.bin", retries=3)

    assert str(excinfo.value) == f"Failed to download {URL} after 3 attempts. Last error: <urlopen error refused 3>"
    assert isinstance(excinfo.value.__cause__, URLError)
    assert excinfo.value.__cause__.reason == "refused 3"
    assert requests == ["HEAD", "GET", "sleep 1.0", "GET", "sleep 2.0", "GET"]


def test_existing_file_of_unknown_size_raises_before_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """An existing destination whose size can't be read is an OSError naming it, and nothing is fetched."""
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"old")
    _serve(monkeypatch, requests, head=lambda: _Response(b"", 5000), get=_no_get)
    monkeypatch.setattr(files, "safe_size", lambda path: None)

    with pytest.raises(OSError) as excinfo:
        files.download_file(URL, dest)

    assert str(excinfo.value) == f"File size is unknown (permissions?): {dest}"
    assert requests == ["HEAD"]
    assert dest.read_bytes() == b"old"


def test_existing_file_of_the_advertised_size_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """A destination already as large as the HEAD size is left alone and not fetched again."""
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"12345")
    _serve(monkeypatch, requests, head=lambda: _Response(b"", 5), get=_no_get)

    files.download_file(URL, dest)

    assert requests == ["HEAD"]
    assert dest.read_bytes() == b"12345"


def test_download_replaces_a_stale_file_with_the_served_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requests: list[str]
) -> None:
    """A destination of the wrong size is downloaded again, and no .part file is left."""
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"old")
    _serve(monkeypatch, requests, head=lambda: _Response(b"", 5), get=lambda n: _Response(b"fresh", 5))

    files.download_file(URL, dest)

    assert requests == ["HEAD", "GET"]
    assert dest.read_bytes() == b"fresh"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data.bin"]
