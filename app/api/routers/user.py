from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.api.deps import require_jwt
from app.core.config import STATS_BASE
from app.schemas.user import LoginRequest, LogoutRequest, SendVcRequest, UserInfoRequest
from app.services import user as svc


class StubMatchName(str, Enum):
    all = "all"
    count = "count"
    stats = "stats"
    win = "win"
    lose = "lose"
    defeat = "defeat"
    history = "history"
    page_info = "pageInfo"


class MatchMode(str, Enum):
    classic    = "classic"
    arcade     = "arcade"
    brawl      = "brawl"
    tournament = "tournament"
    vs         = "vs"
    custom     = "custom"


class HeroStatsWindow(str, Enum):
    w1d  = "1d"
    w3d  = "3d"
    w7d  = "7d"
    w15d = "15d"
    w30d = "30d"


class HeroTrendsWindow(str, Enum):
    w7d  = "7d"
    w15d = "15d"
    w30d = "30d"

router = APIRouter()


def _stats_unavailable() -> None:
    if not STATS_BASE:
        raise HTTPException(
            status_code=503,
            detail="STATS_BASE not configured. See docs/context.md for how to find it.",
        )


def _call(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")


# ---------------------------------------------------------------------------
# Auth endpoints (AUTH_BASE — confirmed working)
# ---------------------------------------------------------------------------

@router.get("/ip", summary="IP geolocation via Moonton (city, country, lang — no auth)")
def ip_geo() -> Any:
    """Returns caller's IP geo info from Moonton: city, state, country code, lang."""
    return _call(svc.get_ip_geo)


@router.get("/rankings", summary="Hero rating polls index (no auth)")
def rankings() -> Any:
    """
    Returns all active hero rating polls (subjects) from the academy.
    Each item: subject (ID), title, desc.
    """
    return _call(svc.get_rankings)


@router.get("/rankings/{subject_id}", summary="Per-subject hero ratings (no auth)")
def rankings_subject(subject_id: str) -> Any:
    """
    Returns the ranked hero list for a specific rating poll subject.
    Each item: object (hero GMS ID), title (hero name), image, image_big.
    Get subject IDs from GET /rankings.
    """
    return _call(svc.get_rankings_subject, subject_id)


@router.get("/server-config", summary="Server time & captcha version (no auth)")
def server_config() -> Any:
    """Public probe — returns Moonton's server Unix time and current captcha version."""
    return _call(svc.get_server_config)


@router.get("/heroes/stats", summary="Hero win/pick/ban rates by time window (no auth)")
def hero_stats(
    window: HeroStatsWindow = Query(default=HeroStatsWindow.w7d, description="Time window: 1d, 3d, 7d, 15d, 30d"),
) -> Any:
    """
    Hero win/pick/ban stats from GMS source 2669606.
    Records keyed by bigrank (1=All, 2=Epic+) and camp_type (0=Classic, 1=Ranked).
    Key fields per record: main_hero.data.{heroid, name}, win_rate, pick_rate, ban_rate.
    """
    return _call(svc.get_hero_stats, window.value)


@router.get("/heroes/combos", summary="Hero skill combos guide (no auth)")
def hero_combos() -> Any:
    """
    Curated hero skill combo guides from GMS source 2669606.
    Each record: caption, configId, data.{_object (hero GMS ID), desc (combo steps)}.
    """
    return _call(svc.get_hero_combos)


@router.get("/heroes/trends", summary="Hero win-rate trend over time (no auth)")
def hero_trends(
    window: HeroTrendsWindow = Query(default=HeroTrendsWindow.w7d, description="Time window: 7d, 15d, 30d"),
) -> Any:
    """
    Daily win_rate / app_rate / ban_rate time series per hero from GMS source 2669606.
    Records keyed by bigrank and camp_type, each with win_rate[] array of per-day values.
    """
    return _call(svc.get_hero_trends, window.value)


@router.get("/catalog/equipment", summary="Full equipment/item catalog — 184 items with id, name, icon (no auth)")
def equipment_catalog() -> Any:
    """
    All 184 equipment items from GMS source 2713644.
    Fields per record: equipid, equipname, equipicon (URL).
    Useful for resolving item IDs in match detail (its[] array) to names and icons.
    """
    return _call(svc.get_equipment_catalog)


@router.get("/catalog/ranks", summary="Rank tier metadata — bigrank IDs mapped to tier names and icons (no auth)")
def rank_tiers() -> Any:
    """
    Maps bigrank integer IDs to their display tier names and sub-rank icons.
    bigrank: 1=Warrior, 2=Elite, 3=Master, 4=Grandmaster, 5=Epic, 6=Legend, 7=Mythic (incl. Honor/Glory/Immortal).
    bigrank 101 = aggregate across all ranks. Also appears in hero stats and lane stats responses.
    """
    return _call(svc.get_rank_tiers)


@router.get("/heroes/stats/by-lane", summary="Hero win rate by lane and rank tier (no auth)")
def hero_lane_stats() -> Any:
    """
    Per-hero win rate broken down by lane and rank tier from GMS source 2713644.
    Fields: hero_name, real_road (1=EXP, 2=Gold, 3=Mid, 4=Jungle, 5=Roam),
    big_rank (5=Epic, 6=Legend, 7=Mythic, 8-9=high Mythic, 101=All),
    total_win_rate, time_win_rate.
    """
    return _call(svc.get_hero_lane_stats)


@router.get("/heroes/catalog", summary="Full hero catalog (name, role, lane, difficulty, portrait — no auth)")
def hero_catalog() -> Any:
    """
    Returns all 132 heroes with name, role, lane, difficulty, specialty, and portrait URLs.
    Data comes from api.gms.moontontech.com. No JWT required.
    Key fields per hero: data.hero.data.{heroid, name, sortlabel, roadsortlabel, difficulty, speciality, head, squarehead}
    """
    return _call(svc.get_hero_catalog)


@router.post("/auth/send-vc", summary="Send verification code to in-game mail")
def send_vc(body: SendVcRequest) -> Any:
    """Step 1 of login. Triggers a 4-digit code to the player's in-game mail (valid 5 min)."""
    return _call(svc.send_vc, body.role_id, body.zone_id)


@router.post("/auth/login", summary="Login with verification code")
def login(body: LoginRequest) -> Any:
    """Step 2 of login. Submit the VC to receive a JWT + session token."""
    return _call(svc.login, body.role_id, body.zone_id, body.vc)


@router.post("/auth/logout", summary="Logout and invalidate JWT")
def logout(
    body: LogoutRequest,
    jwt: Annotated[str, Depends(require_jwt)],
) -> Any:
    return _call(svc.logout, body.role_id, body.zone_id, jwt)


@router.post("/friends/basic", summary="Friend list with names & avatars (AUTH_BASE)")
def friend_list_basic(
    body: UserInfoRequest,
    jwt: Annotated[str, Depends(require_jwt)],
) -> Any:
    """
    Returns all in-game friends with display name, face icon ID, and avatar path.
    Construct full avatar URL as: https://akmpicture.youngjoygame.com/{sFacePath}
    (some friends have empty sFacePath — use iFaceId as fallback icon index).
    Different from GET /friends which returns co-op win-rate stats but hides names.
    """
    return _call(svc.get_friend_list, body.role_id, body.zone_id, jwt)


@router.post("/info", summary="Get player profile (avatar, level, name, rank_level, reg_country)")
def user_info(
    body: UserInfoRequest,
    jwt: Annotated[str, Depends(require_jwt)],
) -> Any:
    return _call(svc.get_user_info, body.role_id, body.zone_id, jwt)


# ---------------------------------------------------------------------------
# Stats endpoints (STATS_BASE — requires STATS_BASE env var)
# ---------------------------------------------------------------------------

_RID_Q = Query(default=None, description="Target player's Game ID (cross-player lookup). Omit for your own data.")
_ZID_Q = Query(default=None, description="Target player's Server ID (required when rid is set).")


@router.get("/stats", summary="Overall player stats (add rid+zid for any player)")
def user_stats(
    jwt: Annotated[str, Depends(require_jwt)],
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    """Career totals: wins, games, avg score, personal records. Pass rid+zid to look up any player."""
    _stats_unavailable()
    return _call(svc.get_stats, jwt, rid, zid)


@router.get("/season", summary="Season list")
def user_season(
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int = Query(default=40, description="Season ID"),
) -> Any:
    _stats_unavailable()
    return _call(svc.get_season, jwt, sid)


@router.get("/matches", summary="Recent matches (add rid+zid for any player, hid to filter by hero)")
def user_matches(
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int = Query(description="Season ID"),
    limit: int = Query(default=10, ge=1, le=100),
    last_cursor: str | None = Query(default=None),
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
    hid: int | None = Query(default=None, description="Filter by hero ID (e.g. 83 = X.Borg)"),
) -> Any:
    """Recent matches. Optional: rid+zid for cross-player, hid to filter to a specific hero."""
    _stats_unavailable()
    return _call(svc.get_matches, jwt, sid, limit, last_cursor, rid, zid, hid)


@router.get("/matches/{match_id}", summary="Match detail")
def match_detail(
    match_id: int,
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int = Query(description="Season ID"),
) -> Any:
    _stats_unavailable()
    return _call(svc.get_match_detail, match_id, sid, jwt)


@router.get("/heroes/frequent", summary="Most played heroes (add rid+zid for any player)")
def frequent_heroes(
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int | None = Query(default=None, description="Season ID (omit for all-time)"),
    limit: int = Query(default=10, ge=1, le=100),
    last_cursor: str | None = Query(default=None),
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    """Most-played heroes. Pass rid+zid to look up any player's hero pool."""
    _stats_unavailable()
    return _call(svc.get_frequent_heroes, jwt, sid, limit, last_cursor, rid, zid)


@router.get("/heroes/{hero_id}/matches", summary="Recent matches with a specific hero (add rid+zid for any player)")
def hero_matches(
    hero_id: int,
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int = Query(description="Season ID"),
    limit: int = Query(default=10, ge=1, le=100),
    last_cursor: str | None = Query(default=None),
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    _stats_unavailable()
    return _call(svc.get_hero_matches, jwt, hero_id, sid, limit, last_cursor, rid, zid)


@router.get("/friends", summary="Friend list with co-op stats (add rid+zid for any player)")
def friends(
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int | None = Query(default=None, description="Season ID (omit for all-time)"),
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    """Co-op friend stats. Pass rid+zid to see another player's friend network."""
    _stats_unavailable()
    return _call(svc.get_friends, jwt, sid, rid, zid)


@router.get("/privacy/settings", summary="Get privacy settings (add rid+zid for any player)")
def privacy_settings(
    jwt: Annotated[str, Depends(require_jwt)],
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    """Check whether a player's profile is public or private."""
    _stats_unavailable()
    return _call(svc.get_privacy_settings, jwt, rid, zid)


@router.post("/privacy/settings", summary="Set profile visibility (visible=true/false)")
def set_privacy(
    jwt: Annotated[str, Depends(require_jwt)],
    visible: bool = Body(..., embed=True, description="true = public profile, false = private"),
) -> Any:
    _stats_unavailable()
    return _call(svc.set_privacy, jwt, visible)


@router.get("/matches/mode/{mode}", summary="Matches by game mode — classic/arcade/brawl/tournament/vs/custom (add rid+zid for any player)")
def mode_matches(
    mode: MatchMode,
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int | None = Query(default=None, description="Season ID (omit for all-time)"),
    limit: int = Query(default=10, ge=1, le=100),
    last_cursor: str | None = Query(default=None),
    rid: int | None = _RID_Q,
    zid: int | None = _ZID_Q,
) -> Any:
    """Match history by game mode. Pass rid+zid to look up any player."""
    _stats_unavailable()
    return _call(svc.get_mode_matches, jwt, mode.value, sid, limit, last_cursor, rid, zid)


@router.get(
    "/matches/stub/{name}",
    summary="Stub match endpoints (registered upstream, return empty result today)",
)
def match_stub(
    name: StubMatchName,
    jwt: Annotated[str, Depends(require_jwt)],
    sid: int | None = Query(default=None, description="Season ID"),
    limit: int = Query(default=10, ge=1, le=100),
    last_cursor: str | None = Query(default=None),
) -> Any:
    """
    Thin pass-throughs for battlereport/matches/{name} paths that exist in Moonton's router
    but currently return {"result": []}. Exposed here so they can be called if Moonton ever
    enables them. Valid names: all, count, stats, win, lose, defeat, history, pageInfo.
    """
    _stats_unavailable()
    return _call(svc.get_match_stub, jwt, name.value, sid, limit, last_cursor)
