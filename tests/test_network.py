"""`is_internet_available`: how the TCP, DNS and HTTP signals combine.

The probes themselves touch the network, so each test replaces them with
fixed answers and checks the verdict against the aggregation rules in the
function's docstring.
"""

from __future__ import annotations

import time

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


def test_http_probe_still_runs_after_tcp_uses_its_whole_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behind a proxy that drops direct TCP, the HTTP probe still gets its own time.

    Fails if the steps share one budget: the TCP step's silent timeouts leave
    nothing for HTTP, so the probe that would succeed is never tried.
    """
    step = 0.6
    probes: list[str] = []

    def tcp_times_out(**_: object) -> bool:
        time.sleep(step)
        return False

    def probe(**kwargs: object) -> tuple[bool, int | None, bytes | None, str | None]:
        probes.append(str(kwargs["url"]))
        return (True, 204, b"", URL)

    monkeypatch.setattr(network, "_run_tcp_checks_with_pool", tcp_times_out)
    monkeypatch.setattr(network, "_any_dns_name_resolves", lambda *_, **__: True)
    monkeypatch.setattr(network, "_build_http_opener", lambda **_: None)
    monkeypatch.setattr(network, "_http_probe_with_cap", probe)

    assert network.is_internet_available(timeout_per_step=step, retries=0) is True
    assert len(probes) == 1


# --- the DNS and TCP phases --------------------------------------------------

def _timed(fn: object, *args: object, **kwargs: object) -> tuple[object, float]:
    """Call fn and return its result with the seconds it took."""
    start = time.monotonic()
    result = fn(*args, **kwargs)  # type: ignore[operator]
    return result, time.monotonic() - start


def test_dns_success_counts_even_after_another_name_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """One name failing quickly doesn't hide another that resolves a moment later.

    Fails if only the first lookup to finish is looked at.
    """
    def resolve(name: str, timeout: float) -> bool:
        if name == "slow-ok":
            time.sleep(0.2)
            return True
        return False

    monkeypatch.setattr(network, "_dns_resolve", resolve)
    assert network._any_dns_name_resolves(["fast-fail", "slow-ok"], per_name_timeout=2.0) is True


def test_dns_answers_without_waiting_for_slow_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """A quick success returns at once instead of waiting out the slow lookups."""
    def resolve(name: str, timeout: float) -> bool:
        if name == "slow":
            time.sleep(2.0)
            return False
        return True

    monkeypatch.setattr(network, "_dns_resolve", resolve)
    result, seconds = _timed(network._any_dns_name_resolves, ["fast-ok", "slow"], per_name_timeout=3.0)
    assert result is True
    assert seconds < 1.0


def test_dns_fails_when_every_name_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """No name resolving means False."""
    monkeypatch.setattr(network, "_dns_resolve", lambda name, timeout: False)
    assert network._any_dns_name_resolves(["a", "b", "c"], per_name_timeout=1.0) is False


def test_tcp_answers_without_waiting_for_slow_connects(monkeypatch: pytest.MonkeyPatch) -> None:
    """One quick connection returns True at once instead of waiting out the slow ones.

    Fails if leaving the thread pool waits for every connect still in flight.
    """
    def connect(host: str, port: int, timeout: float) -> bool:
        if host == "fast":
            return True
        time.sleep(2.0)
        return False

    monkeypatch.setattr(network, "_tcp_connect", connect)
    targets = [("fast", 53), ("slow1", 53), ("slow2", 53)]
    result, seconds = _timed(network._run_tcp_checks_with_pool,
                             tcp_targets=targets, timeout=3.0, requested_workers=3)
    assert result is True
    assert seconds < 1.0
