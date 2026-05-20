"""
Probe the three new upstream endpoint groups discovered from ridwaanhall/api-mobilelegends.

Usage:
    cd /path/to/mlbb-api-own
    JWT=<your_jwt> python scripts/probe_new_endpoints.py
 or python scripts/probe_new_endpoints.py eyJhbGci...

Get JWT via:
    POST /api/user/auth/send-vc  {role_id, zone_id}
    POST /api/user/auth/login    {role_id, zone_id, vc}
    Copy the 'jwt' field from the login response.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AUTH_BASE  = "https://sg-api.mobilelegends.com"
STATS_BASE = "https://app.web.moontontech.com/actgateway"
GMS_ROOT   = "https://api.gms.moontontech.com/api/gms/source/2669606"

HEADERS_COMMON = {
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

TIMEOUT = 10.0
SAMPLE_SUBJECT = "3275335"   # first subject ID seen in reference repo

# Payload variants for GMS POSTs
GMS_PAYLOAD_SIMPLE  = {"pageSize": 200}
GMS_PAYLOAD_ACADEMY = {"pageSize": 200, "pageIndex": 1, "fields": [], "sorts": []}


# ---------------------------------------------------------------------------
# Endpoint definitions
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    name: str
    method: str
    url: str
    auth: bool        # requires JWT
    body: dict | None = None   # POST body; None = GET
    params: dict | None = None
    note: str = ""


def build_probes(jwt: str) -> list[Probe]:
    return [
        # ── AUTH_BASE (no JWT) ──────────────────────────────────────────────
        Probe(
            "ip_geo",
            "GET",
            f"{AUTH_BASE}/c/ip",
            auth=False,
            note="IP geolocation (city/country/lang)",
        ),

        # ── STATS_BASE academy/rankings (JWT required) ──────────────────────
        Probe(
            "academy_rankings",
            "GET",
            f"{STATS_BASE}/academy/rankings",
            auth=True,
            note="Hero rating polls index",
        ),
        Probe(
            f"academy_rankings/{SAMPLE_SUBJECT}",
            "GET",
            f"{STATS_BASE}/academy/rankings/{SAMPLE_SUBJECT}",
            auth=True,
            note="Per-subject hero ratings (sample subject ID)",
        ),

        # ── GMS source 2669606 — hero stat windows ───────────────────────────
        Probe("hero_stats_1d",  "POST", f"{GMS_ROOT}/2756567", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero stats 1-day window"),
        Probe("hero_stats_3d",  "POST", f"{GMS_ROOT}/2756568", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero stats 3-day window"),
        Probe("hero_stats_7d",  "POST", f"{GMS_ROOT}/2756569", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero stats 7-day window"),
        Probe("hero_stats_15d", "POST", f"{GMS_ROOT}/2756565", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero stats 15-day window"),
        Probe("hero_stats_30d", "POST", f"{GMS_ROOT}/2756570", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero stats 30-day window"),

        # ── GMS source 2669606 — hero combos + trends ───────────────────────
        Probe("hero_combos",    "POST", f"{GMS_ROOT}/2674711", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero skill combos"),
        Probe("hero_trends_7d", "POST", f"{GMS_ROOT}/2674709", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero trends 7-day"),
        Probe("hero_trends_15d","POST", f"{GMS_ROOT}/2687909", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero trends 15-day"),
        Probe("hero_trends_30d","POST", f"{GMS_ROOT}/2690860", auth=False, body=GMS_PAYLOAD_SIMPLE, note="Hero trends 30-day"),
    ]


# ---------------------------------------------------------------------------
# Async probe
# ---------------------------------------------------------------------------

@dataclass
class Result:
    probe: Probe
    status: int | str
    body_snippet: str   # first 400 chars, for display
    classification: str
    retry_used: bool = False


def _classify(status: int | str, full_text: str) -> str:
    if not isinstance(status, int):
        return "ERROR"
    if status >= 500:
        return f"HTTP_{status}"
    if status in (401, 403):
        return "AUTH_FAIL"
    if status == 404:
        return "NOT_FOUND"
    if status != 200:
        return f"HTTP_{status}"
    # status 200 — inspect full body
    try:
        data = json.loads(full_text)
        code = data.get("code")
        if code == 0:
            d = data.get("data")
            if d is None:
                return "EMPTY"
            # Check common "empty" shapes: empty list, empty dict, or
            # outer dict whose only list-like child is empty
            if d == [] or d == {}:
                return "EMPTY"
            if isinstance(d, dict):
                inner = d.get("records") or d.get("list") or d.get("data")
                if inner == [] or inner == {}:
                    return "EMPTY"
            return "SUCCESS"
        return f"CODE_{code}"
    except Exception:
        return "200_NOT_JSON"


async def _hit(client: httpx.AsyncClient, sem: asyncio.Semaphore, jwt: str, probe: Probe, use_academy_payload: bool = False) -> tuple[int | str, str, str]:
    """Returns (status, full_text, snippet_400)."""
    headers = {**HEADERS_COMMON}
    if probe.auth:
        headers["authorization"] = jwt
        headers["x-token"] = jwt

    body = probe.body
    if use_academy_payload and body is not None:
        body = GMS_PAYLOAD_ACADEMY

    async with sem:
        try:
            if probe.method == "GET":
                r = await client.get(probe.url, params=probe.params, headers=headers, timeout=TIMEOUT)
            else:
                headers["Content-Type"] = "application/json"
                r = await client.post(probe.url, json=body, headers=headers, timeout=TIMEOUT)
            return r.status_code, r.text, r.text[:400]
        except httpx.TimeoutException:
            return "TIMEOUT", "", ""
        except httpx.ConnectError as e:
            return f"CONN_ERR: {e}", "", ""
        except Exception as e:
            return f"ERR: {e}", "", ""


async def run_probes(jwt: str) -> list[Result]:
    probes = build_probes(jwt)
    sem = asyncio.Semaphore(6)
    results: list[Result] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # First pass
        tasks = [_hit(client, sem, jwt, p) for p in probes]
        first = await asyncio.gather(*tasks)

        for probe, (status, full_text, snippet) in zip(probes, first):
            cls = _classify(status, full_text)
            retry_used = False

            # For GMS POSTs that failed, retry with academy payload
            if probe.method == "POST" and cls not in ("SUCCESS", "EMPTY") and probe.body == GMS_PAYLOAD_SIMPLE:
                status2, full_text2, snippet2 = await _hit(client, sem, jwt, probe, use_academy_payload=True)
                cls2 = _classify(status2, full_text2)
                if cls2 in ("SUCCESS", "EMPTY"):
                    status, snippet, cls = status2, snippet2, cls2
                    retry_used = True

            results.append(Result(probe, status, snippet, cls, retry_used))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    jwt = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JWT", "")
    if not jwt:
        print(
            "No JWT supplied.\n"
            "Usage:  JWT=<token> python scripts/probe_new_endpoints.py\n"
            "     or python scripts/probe_new_endpoints.py <token>"
        )
        sys.exit(1)

    print(f"Probing {11} endpoint candidates ...\n")
    results = asyncio.run(run_probes(jwt))

    success: list[Result] = []
    empty:   list[Result] = []
    failed:  list[Result] = []

    for r in results:
        if r.classification == "SUCCESS":
            success.append(r)
        elif r.classification == "EMPTY":
            empty.append(r)
        else:
            failed.append(r)

    print("=" * 70)
    print(f"SUCCESS ({len(success)}) — these should be wired into the proxy:")
    print("=" * 70)
    for r in success:
        retry = " [academy payload]" if r.retry_used else ""
        print(f"\n  [{r.probe.name}]{retry}")
        print(f"  {r.probe.method} {r.probe.url}")
        print(f"  Note   : {r.probe.note}")
        print(f"  Body   : {r.body_snippet[:250]!r}")

    if empty:
        print(f"\n{'─' * 70}")
        print(f"EMPTY ({len(empty)}) — registered upstream but no data:")
        for r in empty:
            print(f"  {r.probe.name:30s}  {r.probe.url}")

    if failed:
        print(f"\n{'─' * 70}")
        print(f"FAILED ({len(failed)}) — skip these:")
        for r in failed:
            print(f"  [{r.classification:15s}]  {r.probe.name:30s}  {r.probe.url}")
            if r.body_snippet:
                print(f"    body: {r.body_snippet[:120]!r}")

    print(f"\n{'─' * 70}")
    print(f"Total: {len(results)} | SUCCESS: {len(success)} | EMPTY: {len(empty)} | FAILED: {len(failed)}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
