"""`is_internet_available`: how the TCP, DNS and HTTP signals combine.

The probes themselves touch the network, so each test replaces them with
fixed answers and checks the verdict against the aggregation rules in the
function's docstring.
"""

from __future__ import annotations

import pytest

from emmykit import network

URL = "http://www.gstatic.com/generate_204"
PROBE_FAILS = (False, None, None, None)


@pytest.mark.parametrize(
    ("tcp_ok", "dns_ok", "probe", "expected"),
    [
        pytest.param(False, True, (True, 204, b"", URL), True, id="http-probe-passes"),
        pytest.param(True, True, PROBE_FAILS, True, id="tcp-and-dns-without-http"),
        pytest.param(False, True, PROBE_FAILS, False, id="dns-alone"),
        pytest.param(False, False, PROBE_FAILS, False, id="nothing-reachable"),
        pytest.param(True, True, (True, 511, b"", URL), False, id="captive-portal-wins"),
    ],
)
def test_verdict_follows_the_documented_aggregation(
    monkeypatch: pytest.MonkeyPatch,
    tcp_ok: bool,
    dns_ok: bool,
    probe: tuple[bool, int | None, bytes | None, str | None],
    expected: bool,
) -> None:
    """Captive portal → False; HTTP success → True; TCP and DNS → True; DNS alone → False."""
    monkeypatch.setattr(network, "_run_tcp_checks_with_pool", lambda **_: tcp_ok)
    monkeypatch.setattr(network, "_any_dns_name_resolves", lambda *_, **__: dns_ok)
    monkeypatch.setattr(network, "_build_http_opener", lambda **_: None)
    monkeypatch.setattr(network, "_http_probe_with_cap", lambda **_: probe)

    assert network.is_internet_available(retries=0) is expected


@pytest.mark.parametrize(("strict", "expected"), [(False, True), (True, False)])
def test_tcp_alone_counts_only_when_not_strict(
    monkeypatch: pytest.MonkeyPatch, strict: bool, expected: bool
) -> None:
    """Raw TCP with no DNS or HTTP is online by default and not enough when strict."""
    monkeypatch.setattr(network, "_run_tcp_checks_with_pool", lambda **_: True)
    monkeypatch.setattr(network, "_any_dns_name_resolves", lambda *_, **__: False)
    monkeypatch.setattr(network, "_build_http_opener", lambda **_: None)
    monkeypatch.setattr(network, "_http_probe_with_cap", lambda **_: PROBE_FAILS)

    assert network.is_internet_available(retries=0, strict=strict) is expected
