"""`to_jsonable` with an `argparse.Namespace`."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from emmykit.json_io import register_json_type, to_jsonable, unregister_json_type


def test_namespace_without_roundtrip_is_converted_to_plain_json() -> None:
    """Its values are converted too, into a new dict.

    Fails if vars(ns) is handed back as is: a Path in it then breaks
    json.dumps, and the caller can change the namespace through the result.
    """
    ns = argparse.Namespace(out=Path("/tmp/x"), n=3)

    result = to_jsonable(ns, roundtrip=False)

    assert result == {"out": "/tmp/x", "n": 3}
    assert json.dumps(result) == '{"out": "/tmp/x", "n": 3}'
    assert result is not vars(ns)


class _Unencodable:
    """A type whose registered encoder always fails."""


@pytest.fixture
def failing_encoder() -> Iterator[None]:
    """Register an encoder for _Unencodable that raises, for the test's duration."""
    def encode(obj: object) -> dict[str, object]:
        raise RuntimeError("encoder failed")

    register_json_type(_Unencodable, encode)
    yield
    unregister_json_type(_Unencodable)


@pytest.mark.parametrize("wrap", [lambda v: {"k": v}, lambda v: argparse.Namespace(k=v)], ids=["dict", "namespace"])
def test_encoder_errors_inside_a_container_reach_the_caller(
    failing_encoder: None, wrap: object
) -> None:
    """An encoder error inside a Namespace propagates, as it does inside a dict.

    Fails if the Namespace branch swallows it and falls back to str(obj).
    """
    with pytest.raises(RuntimeError, match="encoder failed"):
        to_jsonable(wrap(_Unencodable()))  # type: ignore[operator]
