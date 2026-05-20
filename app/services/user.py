from __future__ import annotations

from typing import Any

from app.core.config import AUTH_BASE, GMS_ACADEMY_ROOT, GMS_BASE, GMS_SOURCE_ROOT, STATS_BASE
from app.core.http import get_json, get_public, post_form, post_form_stats, post_json_public

STUB_MATCH_NAMES = (
    "all", "count", "stats", "win", "lose", "defeat", "history", "pageInfo",
)


# --- AUTH_BASE helpers (confirmed working) ---

def get_server_config() -> Any:
    return post_form(f"{AUTH_BASE}/base/getServerConfig", {})


def send_vc(role_id: int, zone_id: int) -> Any:
    return post_form(f"{AUTH_BASE}/base/sendVc", {"roleId": role_id, "zoneId": zone_id})


def login(role_id: int, zone_id: int, vc: str) -> Any:
    return post_form(f"{AUTH_BASE}/base/login", {
        "roleId": role_id,
        "zoneId": zone_id,
        "vc": vc,
        "referer": "academy",
        "type": "web",
    })


def logout(role_id: int, zone_id: int, jwt: str) -> Any:
    return post_form(f"{AUTH_BASE}/base/logout", {"roleId": role_id, "zoneId": zone_id}, jwt=jwt)


def get_user_info(role_id: int, zone_id: int, jwt: str) -> Any:
    return post_form(
        f"{AUTH_BASE}/base/getBaseInfo",
        {"roleId": role_id, "zoneId": zone_id},
        jwt=jwt,
        for_info=True,
    )


def get_friend_list(role_id: int, zone_id: int, jwt: str) -> Any:
    """AUTH_BASE friend list — returns all friends with name + avatar path.
    Avatar URL = https://akmpicture.youngjoygame.com/{sFacePath} (when sFacePath non-empty).
    Distinct from battlereport/friends which has co-op win rates but hides names."""
    return post_form(
        f"{AUTH_BASE}/base/getFriendList",
        {"roleId": role_id, "zoneId": zone_id},
        jwt=jwt,
        for_info=True,
    )


# --- STATS_BASE helpers (need STATS_BASE env var) ---

def _stats_get(path: str, params: dict[str, Any], jwt: str) -> Any:
    if not STATS_BASE:
        raise RuntimeError("STATS_BASE not configured")
    return get_json(f"{STATS_BASE}/{path}", params, jwt)


def _inject_target(params: dict[str, Any], rid: int | None, zid: int | None) -> dict[str, Any]:
    """Add rid/zid to params when doing a cross-player lookup."""
    if rid is not None:
        params["rid"] = rid
    if zid is not None:
        params["zid"] = zid
    return params


def get_stats(jwt: str, rid: int | None = None, zid: int | None = None) -> Any:
    return _stats_get("battlereport/stats", _inject_target({}, rid, zid), jwt)


def get_season(jwt: str, sid: int) -> Any:
    return _stats_get("battlereport/season/list", {"sid": sid}, jwt)


def get_matches(
    jwt: str,
    sid: int,
    limit: int = 10,
    last_cursor: str | None = None,
    rid: int | None = None,
    zid: int | None = None,
    hid: int | None = None,
) -> Any:
    params: dict[str, Any] = {"sid": sid, "limit": limit}
    if last_cursor:
        params["last_cursor"] = last_cursor
    if hid is not None:
        params["hid"] = hid
    return _stats_get("battlereport/matches/recent", _inject_target(params, rid, zid), jwt)


def get_match_detail(match_id: int, sid: int, jwt: str) -> Any:
    return _stats_get(f"battlereport/matches/{match_id}", {"sid": sid}, jwt)


def get_frequent_heroes(
    jwt: str,
    sid: int | None = None,
    limit: int = 10,
    last_cursor: str | None = None,
    rid: int | None = None,
    zid: int | None = None,
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if sid is not None:
        params["sid"] = sid
    if last_cursor:
        params["last_cursor"] = last_cursor
    return _stats_get("battlereport/heros/frequent", _inject_target(params, rid, zid), jwt)


def get_hero_matches(
    jwt: str,
    hero_id: int,
    sid: int,
    limit: int = 10,
    last_cursor: str | None = None,
    rid: int | None = None,
    zid: int | None = None,
) -> Any:
    params: dict[str, Any] = {"hid": hero_id, "sid": sid, "limit": limit}
    if last_cursor:
        params["last_cursor"] = last_cursor
    return _stats_get("battlereport/hero/matches", _inject_target(params, rid, zid), jwt)


def get_friends(jwt: str, sid: int | None = None, rid: int | None = None, zid: int | None = None) -> Any:
    params: dict[str, Any] = {}
    if sid is not None:
        params["sid"] = sid
    return _stats_get("battlereport/friends", _inject_target(params, rid, zid), jwt)


def get_privacy_settings(jwt: str, rid: int | None = None, zid: int | None = None) -> Any:
    return _stats_get("battlereport/privacy/settings", _inject_target({}, rid, zid), jwt)


def set_privacy(jwt: str, visible: bool) -> Any:
    if not STATS_BASE:
        raise RuntimeError("STATS_BASE not configured")
    return post_form_stats(f"{STATS_BASE}/battlereport/privacy/settings", {"privacy": 2 if visible else 1}, jwt)


def get_hero_catalog() -> Any:
    return post_json_public(GMS_BASE, {"pageSize": 200})


# --- Public extras (no auth required) ---

def get_ip_geo() -> Any:
    return get_public(f"{AUTH_BASE}/c/ip")


def get_rankings() -> Any:
    return get_public(f"{STATS_BASE}/academy/rankings")


def get_rankings_subject(subject_id: str) -> Any:
    return get_public(f"{STATS_BASE}/academy/rankings/{subject_id}")


_HERO_STATS_ID: dict[str, str] = {
    "1d":  "2756567",
    "3d":  "2756568",
    "7d":  "2756569",
    "15d": "2756565",
    "30d": "2756570",
}

_HERO_TRENDS_ID: dict[str, str] = {
    "7d":  "2674709",
    "15d": "2687909",
    "30d": "2690860",
}


def _gms_source_post(endpoint_id: str) -> Any:
    return post_json_public(f"{GMS_SOURCE_ROOT}/{endpoint_id}", {"pageSize": 200})


def get_hero_stats(window: str) -> Any:
    return _gms_source_post(_HERO_STATS_ID[window])


def get_hero_combos() -> Any:
    return _gms_source_post("2674711")


def get_hero_trends(window: str) -> Any:
    return _gms_source_post(_HERO_TRENDS_ID[window])


def _gms_academy_post(endpoint_id: str, page_size: int = 200) -> Any:
    return post_json_public(
        f"{GMS_ACADEMY_ROOT}/{endpoint_id}",
        {"pageSize": page_size},
    )


def get_equipment_catalog() -> Any:
    return _gms_academy_post("2775075", page_size=200)


def get_rank_tiers() -> Any:
    return _gms_academy_post("3210596", page_size=50)


def get_hero_lane_stats() -> Any:
    return _gms_academy_post("2777027", page_size=200)


def get_match_stub(
    jwt: str,
    name: str,
    sid: int | None = None,
    limit: int = 10,
    last_cursor: str | None = None,
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if sid is not None:
        params["sid"] = sid
    if last_cursor:
        params["last_cursor"] = last_cursor
    return _stats_get(f"battlereport/matches/{name}", params, jwt)


def get_mode_matches(
    jwt: str,
    mode: str,
    sid: int | None = None,
    limit: int = 10,
    last_cursor: str | None = None,
    rid: int | None = None,
    zid: int | None = None,
) -> Any:
    params: dict[str, Any] = {"limit": limit}
    if sid is not None:
        params["sid"] = sid
    if last_cursor:
        params["last_cursor"] = last_cursor
    return _stats_get(f"battlereport/matches/{mode}", _inject_target(params, rid, zid), jwt)
