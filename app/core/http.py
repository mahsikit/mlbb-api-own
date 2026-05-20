from __future__ import annotations

import random
from typing import Any

import httpx

from app.core.config import MLBB_ORIGIN, MLBB_REFERER, MLBB_X_ACTID, MLBB_X_APPID

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


def _base_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Origin": MLBB_ORIGIN,
        "Referer": MLBB_REFERER,
        "DNT": "1",
    }


def auth_headers(jwt: str | None = None, *, for_info: bool = False) -> dict[str, str]:
    """Headers for AUTH_BASE form POST calls."""
    h = _base_headers()
    h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    if jwt:
        h["authorization"] = jwt
        h["x-token"] = jwt
    if for_info:
        h["x-actid"] = MLBB_X_ACTID
        h["x-appid"] = MLBB_X_APPID
    return h


def stats_headers(jwt: str) -> dict[str, str]:
    """Headers for STATS_BASE JSON GET calls."""
    h = _base_headers()
    h["Accept"] = "application/json, text/plain, */*"
    h["authorization"] = jwt
    h["x-token"] = jwt
    return h


def post_form(url: str, data: dict[str, Any], jwt: str | None = None, for_info: bool = False) -> Any:
    with httpx.Client(timeout=8) as client:
        r = client.post(url, data=data, headers=auth_headers(jwt, for_info=for_info))
        r.raise_for_status()
        return r.json()


def get_json(url: str, params: dict[str, Any], jwt: str) -> Any:
    with httpx.Client(timeout=8) as client:
        r = client.get(url, params=params, headers=stats_headers(jwt))
        r.raise_for_status()
        return r.json()


def post_form_stats(url: str, data: dict[str, Any], jwt: str) -> Any:
    """Form POST to STATS_BASE (uses stats_headers, not auth_headers)."""
    h = stats_headers(jwt)
    h["Content-Type"] = "application/x-www-form-urlencoded"
    with httpx.Client(timeout=8) as client:
        r = client.post(url, data=data, headers=h)
        r.raise_for_status()
        return r.json()


def get_public(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET with no auth — used for public endpoints like /c/ip, academy/rankings."""
    with httpx.Client(timeout=8) as client:
        r = client.get(url, params=params or {}, headers=_base_headers())
        r.raise_for_status()
        return r.json()


def post_json_public(url: str, body: dict[str, Any]) -> Any:
    """JSON POST with no auth — used for public GMS endpoints."""
    h = _base_headers()
    h["Content-Type"] = "application/json"
    with httpx.Client(timeout=8) as client:
        r = client.post(url, json=body, headers=h)
        r.raise_for_status()
        return r.json()
