"""network — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from emmykit._version import __version__
from emmykit.constants import DEFAULT_ENCODING
from emmykit.net_targets import DNS_TEST_NAMES, HTTP_PROBES, IPV4_TARGETS, IPV6_TARGETS

from collections.abc import Callable
from typing import Any, Final

_EXECUTOR: ThreadPoolExecutor | None = None

def _get_executor() -> ThreadPoolExecutor:
    """Create or return a shared thread pool; never blocks on shutdown."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ud-timer")
        executor  = _EXECUTOR
        assert executor is not None  # for mypy
        import atexit
        atexit.register(executor.shutdown, wait=False, cancel_futures=True)
    assert _EXECUTOR is not None  # for mypy: function guarantees a pool
    return _EXECUTOR

def _call_with_timeout(fn: Callable[..., Any], *args: Any, timeout: float) -> tuple[bool, Any | None]:
    """
    Run fn(*args) in the shared pool and bound wall time.
    Returns (True, result) before the timeout; (False, None) on timeout or error.
    Never waits for the worker to finish if we time out.
    """
    from concurrent.futures import TimeoutError as FutTimeoutError
    pool = _get_executor()
    fut  = pool.submit(fn, *args)
    try:
        return True, fut.result(timeout=timeout)
    except FutTimeoutError as e1:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("call_with_timeout timeout: %r", e1)
        fut.cancel()  # best-effort; we don't join
        return False, None
    except Exception as e2:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("call_with_timeout exception: %r", e2)
        fut.cancel()
        return False, None

def _dns_resolve(name: str, timeout: float) -> bool:
    """
    Try resolving a hostname using the system resolver, but impose a wall-clock cap.

    Args:
        name:    Hostname to resolve.
        timeout: Per-attempt timeout (seconds).

    Returns:
        True if resolution returns at least one address, else False.

    Raises:
        None.
    """
    import socket

    def _work(n: str) -> bool:
        """Perform the actual blocking getaddrinfo call."""
        # Do *not* rely on setdefaulttimeout here; just let getaddrinfo run in a thread.
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("DNS: resolving %s", n)
        res = socket.getaddrinfo(n, None, type=socket.SOCK_STREAM)
        ok  = len(res) > 0
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("DNS: %s for %s", "success" if ok else "empty result", n)
        return ok

    ok, val = _call_with_timeout(_work, name, timeout=timeout)
    if not ok:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("DNS: timeout for %s (>%0.2fs)", name, timeout)
        return False
    return bool(val)

def _any_dns_name_resolves(names: list[str], per_name_timeout: float, max_workers: int = 4) -> bool:
    """
    Resolve several names in parallel; return True on first success or False if all fail/time out.
    The whole phase is bounded by roughly per_name_timeout (not names * timeout).

    Args:
        names:            List of DNS names to resolve.
        per_name_timeout: Timeout (seconds) per name resolution attempt.
        max_workers:      Maximum number of parallel worker threads (default 4).

    Returns:
        True if any name resolves successfully, otherwise False.

    Raises:
        None (errors are caught and logged at DEBUG level).
    """
    from concurrent.futures import wait, FIRST_COMPLETED
    if not names:
        return False
    n_workers = max(1, min(len(names), max_workers))
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("DNS: concurrent phase (%d names, %d workers)", len(names), n_workers)
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(_dns_resolve, n, per_name_timeout) for n in names]
        # Wait once up to per_name_timeout for *any* to finish successfully:
        done, not_done = wait(futures, timeout=per_name_timeout, return_when=FIRST_COMPLETED)
        # Fast check: if any completed True, bail out; otherwise collect late finishes briefly.
        for f in done:
            try:
                if f.result():
                    return True
            except Exception:
                pass
        # Give remaining futures a tiny grace to finish (but don't block long):
        for f in not_done:
            f.cancel()
    return False

def _http_probe_with_cap(url: str, method: str, timeout: float,
                         opener: urllib.request.OpenerDirector
                         ) -> tuple[bool, int | None, bytes | None, str | None]:
    """
    Run _http_probe but bound total wall time (DNS + connect + read).
    """
    def _work() -> tuple[bool, int | None, bytes | None, str | None]:
        """ Call the actual HTTP probe function."""
        return _http_probe(url=url, method=method, timeout=timeout, opener=opener)
    ok, result = _call_with_timeout(_work, timeout=timeout)
    if not ok or result is None:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: timeout for %s %s (>%0.2fs)", method, url, timeout)
        return False, None, None, None
    return result

def _tcp_connect(host: str, port: int, timeout: float) -> bool:
    """
    Attempt a TCP connection to a numeric IP address (no DNS).

    Args:
        host:    Numeric IP address (IPv4/IPv6) as a string.
        port:    Destination TCP port number.
        timeout: Per-attempt timeout (seconds).

    Returns:
        True if TCP connection is successfully established, otherwise False.

    Raises:
        None (errors are caught and logged at DEBUG level).
    """
    import socket
    import ipaddress
    try:
        ip     = ipaddress.ip_address(host)
        family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
        sock   = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "TCP: connecting to %s:%d (timeout=%f)", host, port, timeout
        )
        try:
            sock.connect((host, port))
        finally:
            sock.close()
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("TCP: success %s:%d", host, port)
        return True
    except Exception as exc:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("TCP: failure %s:%d (%s)", host, port, exc)
        return False

def _build_http_opener(ignore_proxies: bool) -> urllib.request.OpenerDirector:
    """
    Build a URL opener honoring or ignoring proxies, with a bound TLS context.

    Args:
        ignore_proxies: Whether to bypass environment proxy settings.

    Returns:
        Configured opener with HTTPSHandler(context=...).
    """
    import ssl
    import urllib.request
    context:  ssl.SSLContext = ssl.create_default_context()
    handlers: list[Any]      = [
        urllib.request.ProxyHandler({} if ignore_proxies else None),  # {} = bypass; None = from env
        urllib.request.HTTPSHandler(context=context),
    ]
    return urllib.request.build_opener(*handlers)

def _http_probe(url: str, method: str, timeout: float,
                opener: urllib.request.OpenerDirector) -> tuple[bool, int | None, bytes | None, str | None]:
    """
    Perform an HTTP(S) probe (HEAD/GET) to a known endpoint.

    Args:
        url:     Target URL.
        method:  HTTP method ('HEAD' or 'GET').
        timeout: Timeout in seconds.
        opener:  Pre-configured opener (proxy/no-proxy).

    Returns:
        (success, status_code, body_bytes_or_None, final_url_if_redirected)

    Raises:
        None.
    """
    import urllib.request
    import urllib.error
    req = urllib.request.Request(url=url, method=method)
    # Add a small UA header to reduce the chance of odd blocks:
    req.add_header("User-Agent", f"{Path(sys.argv[0]).stem}/{__version__} (+python-urllib)")

    try:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: %s %s (timeout=%f)", method, url, timeout)
        with opener.open(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            data   = b""
            final_url = resp.geturl()
            # For HEAD we don't generally read a body; for GET, read up to a ceiling.
            if method.upper() == "GET":
                # Cap read size to avoid hanging on big captive pages.
                data = resp.read(2048)
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: %s %s -> %d, final_url=%s", method, url, status, final_url)
            return True, int(status), data, final_url
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(2048) if hasattr(exc, "read") else None
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: failed to read body from HTTPError: %s", e)
            body = None
        final_url = exc.geturl() if hasattr(exc, "geturl") else None  # ← keep this
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: HTTPError %s %s -> %d", method, url, exc.code)
        return False, int(exc.code), body, final_url
    except Exception as exc:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: failure %s %s (%s)", method, url, exc)
        return False, None, None, None

def _http_meets_expectations(status: int | None, body: bytes | None, expect: dict[str, Any]) -> bool:
    """
    Validate HTTP response against expectations.

    Args:
        status: HTTP status code (or None on failure).
        body:   Response body (None for HEAD or on failure).
        expect: Dict of constraints, e.g.:
                {
                    "status"     : 204,
                    "length_max" : 0,
                    "substr"     : "Microsoft Connect Test",
                }

    Returns:
        True if all applicable expectations are met, else False.

    Raises:
        None.
    """
    if status is None:
        return False

    if "status" in expect and status != int(expect["status"]):
        return False

    if "length_max" in expect and body is not None:
        if len(body) > int(expect["length_max"]):
            return False

    if "substr" in expect and body is not None:
        try:
            text = body.decode(DEFAULT_ENCODING, errors="ignore")
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP: failed to decode body: %s", e)
            text = ""
        if str(expect["substr"]) not in text:
            return False

    return True

def _looks_like_captive(status: int | None, final_url: str | None, body: bytes | None) -> bool:
    """
    Heuristic to detect captive portals:
      - Unexpected 200/30x with HTML body where 204 is expected.
      - Status 511 (Network Authentication Required).
      - Redirects to login/portal-like URLs.

    Args:
        status:    HTTP status (or None).
        final_url: Final URL after redirects (or None).
        body:      Response body (or None).

    Returns:
        True if it appears to be a captive portal, else False.

    Raises:
        None.
    """
    if status is None:
        return False
    if status == 511:   # Network Authentication Required
        return True
    if status in (301, 302, 303, 307, 308):
        return True
    b = (body or b"")[:256].lower()  # bytes, safe for ASCII checks
    if status == 204 and b:
        return True
    if status == 200 and b:
        if b"<html" in b or b"login" in b or b"captive" in b or b"portal" in b:
            return True
    if final_url:
        fu = final_url.casefold()
        if any(k in fu for k in ("login", "captive", "portal", "hotspot", "walledgarden")):
            return True
    return False

def _should_use_proc_cap() -> bool:
    """
    Return True only on POSIX systems where RLIMIT_NPROC is available.
    Avoids calling into Unix-only modules on Windows.
    """
    try:
        import os
        import resource  # type: ignore
        return os.name == "posix" and hasattr(resource, "RLIMIT_NPROC")
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "_should_use_proc_cap: exception checking resource module: %s", e
        )
        return False

def _advisory_user_proc_limit_cap(current_cap: int) -> int:
    """
    Softly cap workers to ~75% of the per-user process limit (where applicable).
    Threads usually don't count as separate "processes" everywhere, so treat this
    as an advisory upper bound, not a guarantee.
    """
    try:
        import resource  # type: ignore
        soft, _hard = resource.getrlimit(resource.RLIMIT_NPROC)
        inf         = getattr(resource, "RLIM_INFINITY", -1)
        # If unlimited or nonsensical, do nothing.
        if soft in (inf, -1) or soft is None or soft <= 0:
            return current_cap
        cap         = max(1, int(soft * 0.75))
        return min(current_cap, cap)
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "_advisory_user_proc_limit_cap: exception checking resource limits: %s", e
        )
        return current_cap

def _effective_workers(requested: int, num_tasks: int, io_bound: bool = True) -> int:
    """
    Choose a sensible max_workers value.

    Args:
        requested: Desired worker count from CLI.
        num_tasks: Number of concurrent tasks you will submit.
        io_bound:  Whether the workload is primarily I/O bound.

    Returns:
        A worker count >= 1 and no larger than the task count and a heuristic cap.

    Raises:
        None
    """
    cpu:       int = os.cpu_count() or 1
    # Heuristic caps: generous for I/O, conservative for CPU-bound.
    cap:       int = 64 if io_bound else max(1, cpu)
    n:         int = min(requested, num_tasks, cap)
    if _should_use_proc_cap():
        n = _advisory_user_proc_limit_cap(n)
    return max(1, n)

def _run_tcp_checks_with_pool(tcp_targets: list[tuple[str, int]],
                              timeout: float, requested_workers: int) -> bool:
    """
    Run the TCP checks using a thread pool with safe sizing and backoff.

    Args:
        tcp_targets:       (host, port) pairs to probe.
        timeout:           Per-connection timeout in seconds.
        requested_workers: CLI-requested max worker count.

    Returns:
        True if any TCP connection succeeded, else False.

    Raises:
        None (creation failures are handled with backoff and logging).
    """
    from concurrent.futures import as_completed
    # 1) Never spawn more workers than concurrent tasks; pick a safe cap.
    n_workers: int = _effective_workers(requested=requested_workers,
                                        num_tasks=len(tcp_targets),
                                        io_bound=True)

    # 2) Backoff plan if the OS refuses to create that many threads.
    #    Try n, then n//2, then 1.
    backoff_plan: list[int] = [n_workers, max(1, n_workers // 2), 1]

    for n in backoff_plan:
        try:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("ThreadPool: attempting max_workers=%d", n)
            with ThreadPoolExecutor(max_workers=n) as pool:
                futures = {pool.submit(_tcp_connect, h, p, timeout): (h, p) for (h, p) in tcp_targets}
                for fut in as_completed(futures):
                    try:
                        if fut.result():
                            try:  # Optional: stop launching/awaiting more work asap
                                pool.shutdown(cancel_futures=True)
                            except TypeError as e:  # Python < 3.9 doesn't support cancel_futures
                                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("ThreadPool: shutdown(cancel_futures=True) not supported: %s", e)
                            return True
                    except Exception as exc:
                        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("TCP: unexpected exception: %s", exc)
            return False
        except (RuntimeError, OSError, MemoryError) as exc:
            logging.warning("Could not start thread pool with %d workers (%s). Trying fewer.", n, exc)
            continue

    # If even 1 worker fails, consider TCP unreachable.
    return False

class CheckResult:
    """Aggregate results from the multi-strategy connectivity check."""
    tcp_ok:           bool
    dns_ok:           bool
    http_ok:          bool
    captive_detected: bool

def _check_once(timeout: float, workers: int, include_ipv6: bool, ignore_proxies: bool) -> CheckResult:
    """
    Perform one pass of the connectivity checks with a total timeout budget.

    Args:
        timeout:        Total timeout budget (seconds) for the entire attempt.
        workers:        Thread pool size for parallel network attempts.
        include_ipv6:   Whether to include IPv6 TCP targets.
        ignore_proxies: If True, bypass env proxies for HTTP probes.

    Returns:
        CheckResult with booleans for TCP, DNS, HTTP, and captive portal detection.

    Raises:
        None.
    """
    import socket
    import time
    start = time.monotonic()

    def _remaining() -> float:
        """
        Return remaining time budget for the current attempt.
        Never return below a small floor to allow some progress.
        """
        # Allow a little budget spread across phases; never below a small floor.
        spent = time.monotonic() - start
        rem = max(0.25, timeout - spent)  # per-attempt budget ~= timeout seconds
        return rem

    tcp_targets: list[tuple[str, int]] = IPV4_TARGETS.copy()
    if include_ipv6 and getattr(socket, "has_ipv6", False):
        tcp_targets.extend(IPV6_TARGETS)

    dns_ok           = False
    http_ok          = False
    captive_detected = False

    # 1) TCP connectivity (already self-bounded by per-connection timeouts)
    tcp_ok = _run_tcp_checks_with_pool(tcp_targets=tcp_targets,
                                       timeout=min(timeout, 5.0),
                                       requested_workers=workers)

    # 2) DNS (parallel, with hard cap ~timeout seconds total for the phase)
    dns_ok = _any_dns_name_resolves(DNS_TEST_NAMES, per_name_timeout=min( max(0.5, _remaining()), timeout))

    # 3) HTTP probes: only try if DNS is healthy (avoids another resolver stall)
    if dns_ok:
        opener = _build_http_opener(ignore_proxies=ignore_proxies)
        for probe in HTTP_PROBES:
            rem = _remaining()
            if rem <= 0.3:
                break  # out of budget for this attempt
            ok, status, body, final_url = _http_probe_with_cap(
                url=probe["url"],
                method=probe["method"],
                timeout=min(rem, timeout),
                opener=opener,
            )
            if ok and _http_meets_expectations(status, body, probe["expect"]):
                http_ok = True
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HTTP probe OK: %s", probe['note'])
                break
            if _looks_like_captive(status, final_url, body):
                captive_detected = True
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                    "Captive portal suspected at %s (status=%s, final_url=%s)", probe['url'], status, final_url
                )
                break

    return CheckResult(
        tcp_ok=tcp_ok,
        dns_ok=dns_ok,
        http_ok=http_ok,
        captive_detected=captive_detected,
    )

def is_internet_available(timeout_per_step: float = 2.5,
                          retries:            int = 1,
                          workers:            int = 6,
                          include_ipv6:      bool = False,
                          strict:            bool = False,
                          ignore_proxies:    bool = False) -> bool:
    """
    Determine if the internet is available using multiple methods.

    Strategy (per attempt):
        1) TCP to multiple well-known numeric IPs (no DNS).
        2) DNS resolution of common hostnames.
        3) HTTP(S) probes with expectations and captive-portal detection.

    Aggregation logic:
        - If captive portal is detected -> return False immediately.
        - If any HTTP probe passes expectations -> return True.
        - Else if TCP OK and DNS OK -> return True.
        - Else:
            * If strict is False and TCP OK alone -> return False
              (raw TCP alone is not considered sufficient for "internet usable").
            * If strict is True -> still False.

    Args:
        timeout_per_step: Timeout (seconds) per individual network attempt.
        retries:          Number of times to repeat the full check if the result is False.
        workers:          Thread pool size for TCP checks.
        include_ipv6:     Whether to include IPv6 targets.
        strict:           Require stronger evidence of connectivity.
        ignore_proxies:   Disable env proxies for HTTP probes.

    Returns:
        True if the internet appears reachable and usable, else False.

    Raises:
        None.
    """
    attempts: int = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(f"Connectivity attempt {attempt}/{attempts}")
        res = _check_once(timeout=timeout_per_step,
                          workers=workers,
                          include_ipv6=include_ipv6,
                          ignore_proxies=ignore_proxies)

        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Result(tcp_ok=%s, dns_ok=%s, http_ok=%s, captive=%s)",
            res.tcp_ok, res.dns_ok, res.http_ok, res.captive_detected
        )

        if res.captive_detected:
            return False

        # HTTP probe success is the strongest positive signal (works with proxies too).
        if res.http_ok:
            return True

        # TCP + DNS (e.g., raw connectivity plus name resolution).
        if res.tcp_ok and res.dns_ok:
            return True

        # Only allow raw TCP success when NOT strict:
        if not strict and res.tcp_ok:
            return True

        # Otherwise, not enough evidence; possibly retry due to transient hiccups.
        if attempt < attempts:
            import time
            import random  # Jitter retries slightly.
            tiny_t: float = 0.05  # seconds
            delay:  float = 2*tiny_t + tiny_t * attempt + random.uniform(0.0, tiny_t)
            time.sleep(delay)
    return False
