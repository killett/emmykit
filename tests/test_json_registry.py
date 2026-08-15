"""Behaviour of the public JSON type registry in emmykit.json_io."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import emmykit as ek
from emmykit import json_io

# Every tag the built-in encoders/decoders already own. Hard-coded here rather
# than imported so the test pins the contract independently of the module.
BUILTIN_TAGS = [
    "path", "tuple", "set", "frozenset", "namespace", "enum",
    "datetime", "date", "time", "decimal", "bytes", "bytearray",
    "memoryview", "recursion", "object", "re_pattern",
]


@pytest.fixture(autouse=True)
def clean_registry() -> Any:
    """Snapshot the registry before each test and restore it afterwards."""
    handlers = list(json_io._JSON_TYPE_HANDLERS)
    tags = dict(json_io._JSON_TAG_HANDLERS)
    yield
    json_io._JSON_TYPE_HANDLERS[:] = handlers
    json_io._JSON_TAG_HANDLERS.clear()
    json_io._JSON_TAG_HANDLERS.update(tags)


@dataclass(frozen=True)
class Point:
    """Hashable stand-in for a consumer's own round-trippable type."""

    x: int
    y: int


def encode_point(obj: Point) -> dict[str, Any]:
    """Encode a Point as a flat payload."""
    return {"x": obj.x, "y": obj.y}


def decode_point(payload: dict[str, Any]) -> Point:
    """Rebuild a Point from a flat payload."""
    return Point(x=payload["x"], y=payload["y"])


def register_point(**kwargs: Any) -> None:
    """Register Point under the 'point' tag with the standard codec."""
    ek.register_json_type(
        Point, encode_point, tag="point", decode=decode_point, **kwargs
    )


def roundtrip_through_json(obj: Any) -> Any:
    """Run obj through to_jsonable -> dumps -> loads -> from_jsonable."""
    return ek.from_jsonable(json.loads(json.dumps(ek.to_jsonable(obj))))


# -------- pre-existing behaviour that must not drift -------- #


def test_unknown_type_tag_keeps_tag_and_decodes_inner_values() -> None:
    """An unrecognized __type__ is passed through with its values decoded."""
    raw = {"__type__": "not_a_known_tag",
           "where": {"__type__": "path", "value": "/tmp/x"},
           "n": 3}
    assert ek.from_jsonable(raw) == {
        "__type__": "not_a_known_tag", "where": Path("/tmp/x"), "n": 3
    }


def test_unregistered_object_still_falls_back_to_str() -> None:
    """With nothing registered, an arbitrary object is stringified as before."""
    p = Point(1, 2)
    assert ek.to_jsonable(p) == {"__type__": "object", "value": str(p)}
    assert ek.to_jsonable(p, roundtrip=False) == str(p)


def test_builtin_types_still_round_trip_with_registry_empty() -> None:
    """The built-in encoders keep working when no custom type is registered."""
    import datetime as dt
    from decimal import Decimal

    original = {"p": Path("/etc/hosts"), "t": (1, 2), "s": {"a"},
                "when": dt.datetime(2026, 6, 6, 12, 0, 0), "d": Decimal("1.5"),
                "b": b"\x00\xff"}
    assert roundtrip_through_json(original) == original


# -------- encode side -------- #


def test_registered_type_round_trips_to_an_equal_object() -> None:
    """A registered type survives dumps/loads and compares equal to the original."""
    register_point()
    assert roundtrip_through_json(Point(3, 4)) == Point(3, 4)


def test_registered_payload_is_flat_and_tagged() -> None:
    """roundtrip=True emits {"__type__": tag, **payload} with no extra nesting."""
    register_point()
    assert ek.to_jsonable(Point(3, 4)) == {"__type__": "point", "x": 3, "y": 4}


def test_registration_wins_over_the_str_fallback() -> None:
    """A registered encoder is consulted before str(), even for a custom __str__."""

    class Loud:
        def __str__(self) -> str:
            return "WRONG"

    ek.register_json_type(Loud, lambda o: {"ok": True}, tag="loud",
                          decode=lambda p: Loud())
    assert ek.to_jsonable(Loud()) == {"__type__": "loud", "ok": True}


def test_registered_objects_nested_in_dict_list_and_set() -> None:
    """Dispatch happens at every depth, not just at the top level."""
    register_point()
    original = {"pairs": [Point(1, 2), Point(3, 4)], "unique": {Point(5, 6)}}
    assert roundtrip_through_json(original) == original


def test_payload_values_are_themselves_converted() -> None:
    """A payload containing a Path and a set is encoded, not inserted raw."""

    @dataclass
    class Conf:
        root: Path
        tags: set[str]

    ek.register_json_type(
        Conf, lambda o: {"root": o.root, "tags": o.tags}, tag="conf",
        decode=lambda p: Conf(root=p["root"], tags=p["tags"]),
    )
    encoded = ek.to_jsonable(Conf(Path("/etc/x"), {"a", "b"}))
    assert encoded["__type__"] == "conf"
    assert encoded["root"] == {"__type__": "path", "value": "/etc/x"}
    assert encoded["tags"]["__type__"] == "set"
    assert sorted(encoded["tags"]["value"]) == ["a", "b"]
    # json.dumps must not raise, and the decoder must receive real objects back.
    restored = ek.from_jsonable(json.loads(json.dumps(encoded)))
    assert restored == Conf(Path("/etc/x"), {"a", "b"})


def test_roundtrip_false_yields_bare_untagged_payload() -> None:
    """roundtrip=False drops the tag entirely."""
    register_point()
    assert ek.to_jsonable(Point(3, 4), roundtrip=False) == {"x": 3, "y": 4}


def test_roundtrip_false_also_untags_nested_payload_values() -> None:
    """The roundtrip flag threads through into the encoder's own payload."""

    class Conf:
        pass

    ek.register_json_type(
        Conf, lambda o: {"root": Path("/etc/x"), "tags": {"a", "b"}},
        tag="conf2", decode=lambda p: Conf(),
    )
    encoded = ek.to_jsonable(Conf(), roundtrip=False)
    assert "__type__" not in encoded
    assert encoded["root"] == "/etc/x"
    assert sorted(encoded["tags"]) == ["a", "b"]


# -------- encode-only registration -------- #


def test_encode_only_registration_is_untagged_and_reloads_as_dict() -> None:
    """No tag and no decode: payload is emitted untagged even under roundtrip=True."""

    class Snapshot:
        pass

    ek.register_json_type(Snapshot, lambda o: {"offline": True, "n": 2})
    encoded = ek.to_jsonable(Snapshot(), roundtrip=True)
    assert encoded == {"offline": True, "n": 2}
    assert ek.from_jsonable(json.loads(json.dumps(encoded))) == {
        "offline": True, "n": 2
    }


def test_tag_without_decode_is_rejected() -> None:
    """A tag with no decoder would write a payload nothing can read back."""
    with pytest.raises(ValueError, match="tag.*decode"):
        ek.register_json_type(Point, encode_point, tag="point")


def test_decode_without_tag_is_rejected() -> None:
    """A decoder with no tag could never be reached on load."""
    with pytest.raises(ValueError, match="tag.*decode"):
        ek.register_json_type(Point, encode_point, decode=decode_point)


# -------- dispatch specificity -------- #


class Base:
    """Registered base class."""


class Derived(Base):
    """Subclass of a registered base class."""


def test_subclass_dispatches_to_the_base_registration() -> None:
    """Dispatch is by isinstance, so a subclass uses the base handler."""
    ek.register_json_type(Base, lambda o: {"kind": "base"}, tag="base",
                          decode=lambda p: Base())
    assert ek.to_jsonable(Derived()) == {"__type__": "base", "kind": "base"}


@pytest.mark.parametrize("base_first", [True, False], ids=["base_first", "sub_first"])
def test_most_specific_class_wins_regardless_of_registration_order(
    base_first: bool,
) -> None:
    """When base and subclass are both registered, the subclass handler wins."""
    reg_base = (Base, lambda o: {"kind": "base"}, "base", lambda p: Base())
    reg_sub = (Derived, lambda o: {"kind": "derived"}, "derived", lambda p: Derived())
    order = [reg_base, reg_sub] if base_first else [reg_sub, reg_base]
    for cls, enc, tag, dec in order:
        ek.register_json_type(cls, enc, tag=tag, decode=dec)
    assert ek.to_jsonable(Derived()) == {"__type__": "derived", "kind": "derived"}
    assert ek.to_jsonable(Base()) == {"__type__": "base", "kind": "base"}


def test_unrelated_matches_tie_break_to_most_recent_registration() -> None:
    """Two equally-specific matches resolve to whichever was registered last."""

    class Left:
        pass

    class Right:
        pass

    class Both(Left, Right):
        pass

    ek.register_json_type(Left, lambda o: {"side": "left"}, tag="left",
                          decode=lambda p: Left())
    ek.register_json_type(Right, lambda o: {"side": "right"}, tag="right",
                          decode=lambda p: Right())
    assert ek.to_jsonable(Both()) == {"__type__": "right", "side": "right"}


# -------- duplicate registration -------- #


def test_duplicate_tag_is_rejected() -> None:
    """Reusing a tag would make the first type's payloads decode as the second."""
    register_point()

    class Other:
        pass

    with pytest.raises(ValueError, match="point"):
        ek.register_json_type(Other, lambda o: {}, tag="point",
                              decode=lambda p: Other())


def test_duplicate_class_is_rejected() -> None:
    """Re-registering a class without replace=True is an error, not a silent swap."""
    register_point()
    with pytest.raises(ValueError, match="Point"):
        ek.register_json_type(Point, encode_point, tag="point2",
                              decode=decode_point)


def test_replace_true_overwrites_the_previous_registration() -> None:
    """replace=True swaps in the new encoder and retires the old tag."""
    register_point()
    ek.register_json_type(Point, lambda o: {"xy": [o.x, o.y]}, tag="point_v2",
                          decode=lambda p: Point(*p["xy"]), replace=True)
    assert ek.to_jsonable(Point(3, 4)) == {"__type__": "point_v2", "xy": [3, 4]}
    # The retired tag is no longer decodable — it behaves as an unknown tag.
    assert ek.from_jsonable({"__type__": "point", "x": 3, "y": 4}) == {
        "__type__": "point", "x": 3, "y": 4
    }


@pytest.mark.parametrize("tag", BUILTIN_TAGS)
def test_builtin_tags_are_rejected(tag: str) -> None:
    """Shadowing a built-in tag would break decoding of Paths, sets, datetimes…"""

    class Squatter:
        pass

    with pytest.raises(ValueError, match="built-in"):
        ek.register_json_type(Squatter, lambda o: {}, tag=tag,
                              decode=lambda p: Squatter())


def test_builtin_tags_are_rejected_even_with_replace() -> None:
    """replace=True is not an escape hatch for built-in tags."""

    class Squatter:
        pass

    with pytest.raises(ValueError, match="built-in"):
        ek.register_json_type(Squatter, lambda o: {}, tag="path",
                              decode=lambda p: Squatter(), replace=True)


# -------- recursion guard -------- #


class Node:
    """Mutable node used to build self-referencing structures."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.link: Any = None
        self.children: list[Any] = []


def register_node() -> None:
    """Register Node with an encoder that walks its own references."""
    ek.register_json_type(
        Node,
        lambda o: {"name": o.name, "link": o.link, "children": o.children},
        tag="node",
        decode=lambda p: Node(p["name"]),
    )


def test_recursion_guard_fires_for_a_direct_self_reference() -> None:
    """A registered encoder must not be able to defeat the _seen guard."""
    register_node()
    n = Node("a")
    n.link = n
    assert ek.to_jsonable(n) == {
        "__type__": "node", "name": "a",
        "link": {"__type__": "recursion"}, "children": [],
    }


def test_recursion_guard_fires_through_a_list_mediated_cycle() -> None:
    """A -> [B] -> [A] terminates instead of recursing forever."""
    register_node()
    a, b = Node("a"), Node("b")
    a.children.append(b)
    b.children.append(a)
    encoded = ek.to_jsonable(a)
    assert encoded["children"][0]["children"][0] == {"__type__": "recursion"}


# -------- unregistration -------- #


def test_unregister_by_class_restores_the_str_fallback() -> None:
    """Removing a handler puts the type back on the pre-registration path."""
    register_point()
    ek.unregister_json_type(Point)
    p = Point(1, 2)
    assert ek.to_jsonable(p) == {"__type__": "object", "value": str(p)}


def test_unregister_by_tag_removes_the_handler() -> None:
    """A registration can be retired by tag as well as by class."""
    register_point()
    ek.unregister_json_type("point")
    p = Point(1, 2)
    assert ek.to_jsonable(p) == {"__type__": "object", "value": str(p)}
    assert ek.from_jsonable({"__type__": "point", "x": 1, "y": 2}) == {
        "__type__": "point", "x": 1, "y": 2
    }


def test_unregister_unknown_target_raises() -> None:
    """Silently ignoring a bad unregister would hide typos in teardown code."""
    with pytest.raises(KeyError):
        ek.unregister_json_type("never_registered")
    with pytest.raises(KeyError):
        ek.unregister_json_type(Point)


def test_unregister_rejects_a_non_class_non_string() -> None:
    """Passing an *instance* by mistake must not be read as 'nothing registered'."""
    register_point()
    with pytest.raises(TypeError, match="class or a tag string"):
        ek.unregister_json_type(Point(1, 2))


# -------- argument validation -------- #


def test_registering_a_non_class_is_rejected() -> None:
    """Passing an instance instead of the class would never match isinstance."""
    with pytest.raises(TypeError, match="cls must be a class"):
        ek.register_json_type(Point(1, 2), encode_point, tag="p",
                              decode=decode_point)


def test_non_callable_encode_is_rejected() -> None:
    """A non-callable encoder would only blow up at serialization time."""
    with pytest.raises(TypeError, match="encode must be callable"):
        ek.register_json_type(Point, {"x": 1}, tag="p", decode=decode_point)


def test_non_callable_decode_is_rejected() -> None:
    """A non-callable decoder would only blow up at load time."""
    with pytest.raises(TypeError, match="decode must be callable"):
        ek.register_json_type(Point, encode_point, tag="p", decode="nope")


def test_empty_tag_is_rejected() -> None:
    """An empty tag would serialize as `"__type__": ""` and never decode."""
    with pytest.raises(ValueError, match="non-empty string"):
        ek.register_json_type(Point, encode_point, tag="", decode=decode_point)


def test_replace_retires_a_tag_held_by_a_different_class() -> None:
    """replace=True must free the tag from its previous owner, not double-book it."""
    register_point()

    class Other:
        pass

    ek.register_json_type(Other, lambda o: {"kind": "other"}, tag="point",
                          decode=lambda p: Other(), replace=True)
    assert ek.to_jsonable(Other()) == {"__type__": "point", "kind": "other"}
    # Point lost its handler along with the tag and is back on the str() path.
    p = Point(1, 2)
    assert ek.to_jsonable(p) == {"__type__": "object", "value": str(p)}


def test_encoder_returning_a_non_mapping_is_rejected() -> None:
    """A list-returning encoder must fail loudly, not emit an unusable payload."""

    class Bad:
        pass

    ek.register_json_type(Bad, lambda o: ["not", "a", "mapping"], tag="bad",
                          decode=lambda p: Bad())
    with pytest.raises(TypeError, match="expected a mapping"):
        ek.to_jsonable(Bad())
