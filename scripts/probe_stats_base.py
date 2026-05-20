"""
One-off probe script to find STATS_BASE by trying path-prefix permutations on
all known-live Moonton/MLBB hosts.

Usage:
    cd /path/to/mlbb-api-own
    JWT=<your_jwt> python scripts/probe_stats_base.py

Or paste the JWT as a CLI arg:
    python scripts/probe_stats_base.py eyJhbGci...

The script probes:
    https://{host}{prefix}/battlereport/matches/recent?sid=40&limit=5

and classifies each response. Any non-404 is flagged immediately.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import NamedTuple

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOSTS = [
    "sg-api.mobilelegends.com",
    "api.gms.moontontech.com",
    "act.gms.moontontech.com",
    "api.moba5v5.com",
]

# Prefixes NOT yet tried according to docs/stats-base-research.md
PREFIXES: list[str] = [
    # No prefix (already tried on all 4, but include for completeness)
    "",
    # Version prefixes
    "/v1",
    "/v2",
    "/api/v1",
    "/api/v2",
    # Report variants
    "/report",
    "/api/report",
    "/api/v1/report",
    "/api/v2/report",
    # User variants
    "/user",
    "/api/user",
    "/api/v1/user",
    # Brand/platform
    "/mlbb",
    "/api/mlbb",
    "/m",
    "/api/m",
    "/web",
    "/api/web",
    # Region
    "/sg",
    "/api/sg",
    "/game",
    "/api/game",
    # GMS/Act variants
    "/gms",
    "/api/gms",
    "/act/v1",
    "/act/v2",
    "/v1/act",
    "/v2/act",
    "/api/v1/act",
    # Battle
    "/battle",
    "/api/battle",
    "/battlestats",
    "/api/battlestats",
    # Already tried (kept here to verify consistent 404 as a baseline)
    "/api",
    "/api/act",
    "/act",
    "/actgateway",
    "/api/actgateway",
]

TEST_PATH = "battlereport/matches/recent"
TEST_PARAMS = {"sid": "40", "limit": "5"}

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.mobilelegends.com",
    "Referer": "https://www.mobilelegends.com/",
    "DNT": "1",
}

TIMEOUT = 8.0
CONCURRENCY = 10  # parallel probes — be polite to Moonton's servers


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class ProbeResult(NamedTuple):
    host: str
    prefix: str
    status: int | str   # int on HTTP response, string on network error
    body_snippet: str
    server: str


def classify(r: ProbeResult) -> str:
    if isinstance(r.status, str):
        return "ERROR"
    if r.status == 200:
        if '"code"' in r.body_snippet:
            return "SUCCESS"
        return "200_UNKNOWN"
    if r.status in (401, 403):
        return "AUTH_HIT"   # right server, wrong/no auth — chase this
    if r.status == 400:
        return "BAD_REQUEST"  # right server, wrong params — chase this
    if r.status == 404:
        return "MISS"
    return f"HTTP_{r.status}"


# ---------------------------------------------------------------------------
# Async probe
# ---------------------------------------------------------------------------

async def probe_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    jwt: str,
    host: str,
    prefix: str,
) -> ProbeResult:
    url = f"https://{host}{prefix}/{TEST_PATH}"
    headers = {**HEADERS_BASE, "authorization": jwt, "x-token": jwt}
    async with sem:
        try:
            resp = await client.get(url, params=TEST_PARAMS, headers=headers, timeout=TIMEOUT)
            body = resp.text[:300]
            server = resp.headers.get("server", "")
            return ProbeResult(host, prefix, resp.status_code, body, server)
        except httpx.TimeoutException:
            return ProbeResult(host, prefix, "TIMEOUT", "", "")
        except httpx.ConnectError as e:
            return ProbeResult(host, prefix, f"CONN_ERR: {e}", "", "")
        except Exception as e:
            return ProbeResult(host, prefix, f"ERR: {e}", "", "")


async def run(jwt: str) -> list[ProbeResult]:
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for host in HOSTS:
            for prefix in PREFIXES:
                tasks.append(probe_one(client, sem, jwt, host, prefix))
        results = await asyncio.gather(*tasks)
    return list(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    jwt = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JWT", "")
    if not jwt:
        print(
            "No JWT supplied.\n"
            "Usage:  JWT=<token> python scripts/probe_stats_base.py\n"
            "     or python scripts/probe_stats_base.py <token>\n"
            "\n"
            "Get a token via the proxy:\n"
            "  POST /api/user/auth/send-vc  {role_id, zone_id}\n"
            "  POST /api/user/auth/login    {role_id, zone_id, vc}\n"
            "  Then copy the 'jwt' field from the response."
        )
        sys.exit(1)

    print(
        f"Probing {len(HOSTS)} hosts × {len(PREFIXES)} prefixes "
        f"= {len(HOSTS) * len(PREFIXES)} requests ...\n"
        f"Test path: /{TEST_PATH}?sid=40&limit=5\n"
    )

    results = asyncio.run(run(jwt))

    hits: list[ProbeResult] = []
    misses: list[ProbeResult] = []

    for r in results:
        c = classify(r)
        if c != "MISS":
            hits.append(r)
        else:
            misses.append(r)

    # Print non-miss results first
    if hits:
        print("=" * 70)
        print("NON-404 RESULTS (investigate these):")
        print("=" * 70)
        for r in hits:
            c = classify(r)
            base = f"https://{r.host}{r.prefix}"
            print(f"\n[{c}]  {base}")
            print(f"  Status : {r.status}")
            print(f"  Server : {r.server}")
            print(f"  Body   : {r.body_snippet[:200]!r}")
            if c == "SUCCESS":
                print(f"\n{'*' * 60}")
                print(f"  *** STATS_BASE FOUND: {base} ***")
                print(f"{'*' * 60}")
    else:
        print("No non-404 results. All prefixes returned 404 or errors.")

    # Summary table
    print("\n" + "-" * 70)
    print(f"Total probes: {len(results)}")
    print(f"  Non-404  : {len(hits)}")
    print(f"  404/miss : {len(misses)}")

    # Detailed miss listing (verbose for the research doc)
    if "--verbose" in sys.argv or "-v" in sys.argv:
        print("\n--- MISS LIST (for docs/stats-base-research.md) ---")
        for r in sorted(misses, key=lambda x: (x.host, x.prefix)):
            print(f"  {r.status}  https://{r.host}{r.prefix}/{TEST_PATH}")

    if any(classify(r) == "SUCCESS" for r in results):
        sys.exit(0)
    elif hits:
        print("\nPartial hits above — investigate manually. Exiting with code 2.")
        sys.exit(2)
    else:
        print("\nAll miss. Consider pivoting to Priority 2 (Wayback Machine JS recovery).")
        sys.exit(1)


if __name__ == "__main__":
    main()
