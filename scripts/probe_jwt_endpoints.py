"""
Probe candidate JWT-required endpoints on AUTH_BASE and STATS_BASE.

IMPORTANT: must be run with a real JWT — without one, actgateway returns HTTP 200
with code:1002 for every path, which is a false positive.

Usage:
    JWT=<your_jwt> python scripts/probe_jwt_endpoints.py
 or python scripts/probe_jwt_endpoints.py eyJhbGci...

Get JWT:
    POST /api/user/auth/send-vc  {role_id, zone_id}
    POST /api/user/auth/login    {role_id, zone_id, vc}
    copy 'jwt' from response
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field

import httpx

# ---------------------------------------------------------------------------
# Hosts
# ---------------------------------------------------------------------------

AUTH_BASE  = "https://sg-api.mobilelegends.com"
STATS_BASE = "https://app.web.moontontech.com/actgateway"

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Origin": "https://www.mobilelegends.com",
    "Referer": "https://www.mobilelegends.com/",
    "DNT": "1",
}

TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# Probe definitions
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    name: str
    method: str      # GET | POST
    url: str
    body: dict | None = None    # form data for POST
    params: dict | None = None  # query params for GET
    extra_headers: dict = field(default_factory=dict)
    note: str = ""


def build_probes(jwt: str, role_id: str = "0", zone_id: str = "0") -> list[Probe]:
    """
    role_id / zone_id: pass real values if available for POST endpoints that need them.
    Defaults to "0" which will likely fail gracefully (wrong params ≠ wrong path).
    """
    form = {"roleId": role_id, "zoneId": zone_id}
    info_headers = {"x-actid": "2728785", "x-appid": "2713644"}

    return [
        # ── AUTH_BASE /base/* (form-POST, JWT in headers) ────────────────────
        Probe("checkLogin",        "POST", f"{AUTH_BASE}/base/checkLogin",        body=form, note="Check if JWT is still valid"),
        Probe("getRankInfo",       "POST", f"{AUTH_BASE}/base/getRankInfo",        body=form, note="Player rank/MMR info"),
        Probe("getSeasonInfo",     "POST", f"{AUTH_BASE}/base/getSeasonInfo",      body=form, note="Season standing"),
        Probe("getRoleInfo",       "POST", f"{AUTH_BASE}/base/getRoleInfo",        body=form, note="Extended role/game info"),
        Probe("getZoneList",       "POST", f"{AUTH_BASE}/base/getZoneList",        body={},   note="List of game servers/zones"),
        Probe("getGuildInfo",      "POST", f"{AUTH_BASE}/base/getGuildInfo",       body=form, note="Guild membership info"),
        Probe("getHonorInfo",      "POST", f"{AUTH_BASE}/base/getHonorInfo",       body=form, note="Credit/honor score"),
        Probe("getCreditScore",    "POST", f"{AUTH_BASE}/base/getCreditScore",     body=form, note="Credit score"),
        Probe("getAchievement",    "POST", f"{AUTH_BASE}/base/getAchievement",     body=form, note="Achievement list"),
        Probe("getMedalInfo",      "POST", f"{AUTH_BASE}/base/getMedalInfo",       body=form, note="Medal/emblem info"),
        Probe("getTitle",          "POST", f"{AUTH_BASE}/base/getTitle",           body=form, note="Player titles"),
        Probe("getPlayerCard",     "POST", f"{AUTH_BASE}/base/getPlayerCard",      body=form, note="Player profile card"),
        Probe("queryFriend",       "POST", f"{AUTH_BASE}/base/queryFriend",        body=form, note="Query a friend's info"),
        Probe("getSkinInfo",       "POST", f"{AUTH_BASE}/base/getSkinInfo",        body=form, note="Owned skin list"),
        Probe("getHeroInfo",       "POST", f"{AUTH_BASE}/base/getHeroInfo",        body=form, note="Owned hero list"),
        Probe("getEquipInfo",      "POST", f"{AUTH_BASE}/base/getEquipInfo",       body=form, note="Equipment/item info"),
        Probe("getLoginLog",       "POST", f"{AUTH_BASE}/base/getLoginLog",        body=form, note="Login history"),
        Probe("getUserGameRole",   "POST", f"{AUTH_BASE}/base/getUserGameRole",    body=form, note="Game role details"),
        Probe("getRegionList",     "POST", f"{AUTH_BASE}/base/getRegionList",      body={},   note="Region list"),
        Probe("getNotice",         "POST", f"{AUTH_BASE}/base/getNotice",          body=form, note="In-game notices"),
        Probe("getMailList",       "POST", f"{AUTH_BASE}/base/getMailList",        body=form, note="In-game mail list"),
        Probe("getBattleReport",   "POST", f"{AUTH_BASE}/base/getBattleReport",    body=form, note="Battle report"),
        Probe("getMatchRecord",    "POST", f"{AUTH_BASE}/base/getMatchRecord",     body=form, note="Match records"),
        Probe("getFavoriteHero",   "POST", f"{AUTH_BASE}/base/getFavoriteHero",    body=form, note="Favorite heroes"),
        Probe("getProfile",        "POST", f"{AUTH_BASE}/base/getProfile",         body=form, extra_headers=info_headers, note="Full profile"),
        Probe("getPlayerInfo",     "POST", f"{AUTH_BASE}/base/getPlayerInfo",      body=form, extra_headers=info_headers, note="Player info extended"),
        Probe("getSeasonRecord",   "POST", f"{AUTH_BASE}/base/getSeasonRecord",    body={**form, "sid": "40"}, note="Per-season record"),
        Probe("getHeroRecord",     "POST", f"{AUTH_BASE}/base/getHeroRecord",      body=form, note="Hero usage record"),
        Probe("getRankRecord",     "POST", f"{AUTH_BASE}/base/getRankRecord",      body=form, note="Ranked game record"),

        # ── STATS_BASE battlereport/* (GET, JWT in headers) ─────────────────
        Probe("br/rank/info",          "GET", f"{STATS_BASE}/battlereport/rank/info",         note="Rank details (MMR, tier)"),
        Probe("br/rank/list",          "GET", f"{STATS_BASE}/battlereport/rank/list",         note="Rank leaderboard"),
        Probe("br/credit/score",       "GET", f"{STATS_BASE}/battlereport/credit/score",      note="Credit score"),
        Probe("br/credit",             "GET", f"{STATS_BASE}/battlereport/credit",            note="Credit info"),
        Probe("br/achievement",        "GET", f"{STATS_BASE}/battlereport/achievement",       note="Achievement list"),
        Probe("br/achievement/list",   "GET", f"{STATS_BASE}/battlereport/achievement/list",  note="Achievement list alt"),
        Probe("br/mvp",                "GET", f"{STATS_BASE}/battlereport/mvp",               note="MVP record"),
        Probe("br/mvp/list",           "GET", f"{STATS_BASE}/battlereport/mvp/list",          note="MVP list"),
        Probe("br/guild",              "GET", f"{STATS_BASE}/battlereport/guild",             note="Guild info"),
        Probe("br/guild/info",         "GET", f"{STATS_BASE}/battlereport/guild/info",        note="Guild info alt"),
        Probe("br/profile",            "GET", f"{STATS_BASE}/battlereport/profile",           note="Player profile"),
        Probe("br/summary",            "GET", f"{STATS_BASE}/battlereport/summary",           note="Overall summary"),
        Probe("br/season/stats",       "GET", f"{STATS_BASE}/battlereport/season/stats",      note="Season stats"),
        Probe("br/season/info",        "GET", f"{STATS_BASE}/battlereport/season/info",       note="Season info"),
        Probe("br/hero/stats",         "GET", f"{STATS_BASE}/battlereport/hero/stats",        note="Hero stats"),
        Probe("br/hero/detail",        "GET", f"{STATS_BASE}/battlereport/hero/detail",       note="Hero detail"),
        Probe("br/hero/list",          "GET", f"{STATS_BASE}/battlereport/hero/list",         note="Hero list"),
        Probe("br/heros/stats",        "GET", f"{STATS_BASE}/battlereport/heros/stats",       note="Heroes stats alt"),
        Probe("br/heros/list",         "GET", f"{STATS_BASE}/battlereport/heros/list",        note="Heroes list"),
        Probe("br/matches/classic",    "GET", f"{STATS_BASE}/battlereport/matches/classic",   note="Classic mode matches"),
        Probe("br/matches/arcade",     "GET", f"{STATS_BASE}/battlereport/matches/arcade",    note="Arcade mode matches"),
        Probe("br/matches/brawl",      "GET", f"{STATS_BASE}/battlereport/matches/brawl",     note="Brawl mode matches"),
        Probe("br/matches/tournament", "GET", f"{STATS_BASE}/battlereport/matches/tournament",note="Tournament matches"),
        Probe("br/matches/vs",         "GET", f"{STATS_BASE}/battlereport/matches/vs",        note="VS AI matches"),
        Probe("br/matches/custom",     "GET", f"{STATS_BASE}/battlereport/matches/custom",    note="Custom room matches"),
        Probe("br/friends/list",       "GET", f"{STATS_BASE}/battlereport/friends/list",      note="Friend list alt"),
        Probe("br/friends/stats",      "GET", f"{STATS_BASE}/battlereport/friends/stats",     note="Friend stats"),
        Probe("br/medal",              "GET", f"{STATS_BASE}/battlereport/medal",             note="Medal info"),
        Probe("br/medal/list",         "GET", f"{STATS_BASE}/battlereport/medal/list",        note="Medal list"),
        Probe("br/title",              "GET", f"{STATS_BASE}/battlereport/title",             note="Player titles"),
        Probe("br/skin",               "GET", f"{STATS_BASE}/battlereport/skin",              note="Owned skins"),
        Probe("br/skin/list",          "GET", f"{STATS_BASE}/battlereport/skin/list",         note="Skin list"),
        Probe("br/hero/frequent",      "GET", f"{STATS_BASE}/battlereport/hero/frequent",     note="Frequent heroes alt path"),
        Probe("br/heros/rank",         "GET", f"{STATS_BASE}/battlereport/heros/rank",        note="Heroes ranked"),
        Probe("br/privacy",            "GET", f"{STATS_BASE}/battlereport/privacy",           note="Privacy (shorter path)"),
        Probe("br/notification",       "GET", f"{STATS_BASE}/battlereport/notification",      note="Notifications"),
        Probe("br/season/rank",        "GET", f"{STATS_BASE}/battlereport/season/rank",       note="Season rank"),
        Probe("br/classic/stats",      "GET", f"{STATS_BASE}/battlereport/classic/stats",     note="Classic stats"),
        Probe("br/rank",               "GET", f"{STATS_BASE}/battlereport/rank",              note="Rank (short path)"),
    ]


# ---------------------------------------------------------------------------
# Async hit
# ---------------------------------------------------------------------------

async def _hit(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    jwt: str,
    probe: Probe,
) -> tuple[int | str, str, str]:
    headers = {
        **HEADERS_BASE,
        **probe.extra_headers,
        "authorization": jwt,
        "x-token": jwt,
    }

    async with sem:
        try:
            if probe.method == "GET":
                r = await client.get(probe.url, params=probe.params, headers=headers, timeout=TIMEOUT)
            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                r = await client.post(probe.url, data=probe.body, headers=headers, timeout=TIMEOUT)
            return r.status_code, r.text, r.text[:350]
        except httpx.TimeoutException:
            return "TIMEOUT", "", ""
        except httpx.ConnectError as e:
            return f"CONN_ERR: {e}", "", ""
        except Exception as e:
            return f"ERR: {e}", "", ""


def _classify(status: int | str, full_text: str) -> str:
    if not isinstance(status, int):
        return "ERROR"
    if status == 404:
        return "NOT_FOUND"
    if status in (401, 403):
        return "AUTH_FAIL"
    if status >= 500:
        return f"HTTP_{status}"
    if status != 200:
        return f"HTTP_{status}"
    try:
        d = json.loads(full_text)
        code = d.get("code")
        if code == 0:
            data = d.get("data") or d.get("result")
            if data is None or data == [] or data == {}:
                return "EMPTY"
            if isinstance(data, dict):
                inner = data.get("records") or data.get("list") or data.get("data")
                if inner == [] or inner == {}:
                    return "EMPTY"
            return "SUCCESS"
        if code == 1002:
            return "AUTH_EMPTY"   # middleware false-positive — means no JWT was seen
        if code == 1001:
            return "AUTH_INVALID"
        return f"CODE_{code}"
    except Exception:
        return "200_NOT_JSON"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

async def run(jwt: str, role_id: str, zone_id: str) -> list[tuple[Probe, str, str, str]]:
    probes = build_probes(jwt, role_id, zone_id)
    sem = asyncio.Semaphore(8)
    results = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [_hit(client, sem, jwt, p) for p in probes]
        raw = await asyncio.gather(*tasks)
    for probe, (status, full, snippet) in zip(probes, raw):
        cls = _classify(status, full)
        results.append((probe, str(status), snippet, cls))
    return results


def main() -> None:
    jwt = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JWT", "")
    role_id = os.environ.get("ROLE_ID", "0")
    zone_id = os.environ.get("ZONE_ID", "0")

    if not jwt:
        print(
            "No JWT. Usage:\n"
            "  JWT=<token> python scripts/probe_jwt_endpoints.py\n"
            "  JWT=<token> ROLE_ID=<gameid> ZONE_ID=<serverid> python scripts/probe_jwt_endpoints.py\n\n"
            "Get JWT: POST /api/user/auth/send-vc → /api/user/auth/login"
        )
        sys.exit(1)

    print(f"Probing {len(build_probes(jwt))} JWT-gated endpoint candidates …\n")
    results = asyncio.run(run(jwt, role_id, zone_id))

    by_class: dict[str, list] = {}
    for item in results:
        cls = item[3]
        by_class.setdefault(cls, []).append(item)

    def _show(label: str, keys: list[str]) -> None:
        items = []
        for k in keys:
            items.extend(by_class.get(k, []))
        if not items:
            return
        total = sum(len(by_class.get(k, [])) for k in keys)
        print("=" * 70)
        print(f"{label} ({total}):")
        print("=" * 70)
        for probe, status, snippet, cls in items:
            print(f"\n  [{cls}]  {probe.name}")
            print(f"  {probe.method} {probe.url}")
            print(f"  Note  : {probe.note}")
            if snippet:
                print(f"  Body  : {snippet!r}")

    _show("SUCCESS — wire these up", ["SUCCESS"])
    _show("EMPTY — registered but no data (stub-like)", ["EMPTY"])
    _show("WRONG PARAMS — endpoint exists, adjust body/params", ["CODE_4", "CODE_5", "CODE_1", "CODE_10", "CODE_100"])

    # Show any unexpected non-404 codes
    unexpected = []
    skip = {"SUCCESS", "EMPTY", "NOT_FOUND", "AUTH_EMPTY", "AUTH_INVALID", "TIMEOUT", "ERROR"}
    for k, v in by_class.items():
        if k not in skip and not k.startswith("CODE_") and k not in ("AUTH_FAIL",):
            unexpected.extend(v)
    if unexpected:
        print("\n" + "=" * 70)
        print(f"UNEXPECTED ({len(unexpected)}) — investigate:")
        print("=" * 70)
        for probe, status, snippet, cls in unexpected:
            print(f"  [{cls}]  {probe.name}  →  {snippet[:150]!r}")

    print("\n" + "─" * 70)
    for cls, items in sorted(by_class.items()):
        print(f"  {cls:20s}: {len(items)}")
    print("─" * 70)
    print(f"  {'TOTAL':20s}: {len(results)}")

    if by_class.get("SUCCESS") or by_class.get("EMPTY"):
        sys.exit(0)
    else:
        print("\nNo hits. Check that JWT is valid (not expired) and try with real ROLE_ID/ZONE_ID.")
        sys.exit(1)


if __name__ == "__main__":
    main()
