"""net_targets — extracted from univ_defs.py."""

from __future__ import annotations

IPV4_TARGETS: list[tuple[str, int]] = [
    ("1.1.1.1",        443),  # Cloudflare
    ("8.8.8.8",        853),  # Google Public DNS over TLS (TCP)
    ("9.9.9.9",        443),  # Quad9
    ("208.67.222.222", 443),  # Cisco OpenDNS
]

IPV6_TARGETS: list[tuple[str, int]] = [
    ("2606:4700:4700::1111", 443),  # Cloudflare
    ("2001:4860:4860::8888",  53),  # Google Public DNS (TCP)
]

HTTP_PROBES: list[dict[str, Any]] = [
    {
        "url"    : "https://www.gstatic.com/generate_204",
        "method" : "GET",
        "expect" : {"status": 204},
        "note"   : "Android/gstatic 204 probe",
    },
    {
        "url"    : "http://www.gstatic.com/generate_204",
        "method" : "GET",
        "expect" : {"status": 204, "length_max": 0},
        "note"   : "HTTP 204 (checks for captive portal redirects)",
    },
    {
        "url"     : "http://www.msftconnecttest.com/connecttest.txt",
        "method"  : "GET",
        "expect"  : {"status": 200, "substr": "Microsoft Connect Test"},
        "note"    : "Microsoft connect test",
    },
]

DNS_TEST_NAMES: list[str] = [
    "example.com",      # IANA
    "cloudflare.com",   # Cloudflare
    "google.com",       # Google
    "one.one.one.one",  # Cloudflare DNS name (usually uncached locally)
    "dns.google",       # Google DNS name
]
