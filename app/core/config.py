from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Upstream MLBB API bases
# AUTH_BASE: confirmed from DevTools — handles sendVc, login, logout, getBaseInfo
AUTH_BASE: str = os.environ.get("AUTH_BASE", "https://sg-api.mobilelegends.com")

# STATS_BASE: needed for all battlereport/* endpoints (stats, matches, season, etc.)
# Still unknown — capture mobile app traffic with Charles Proxy / mitmproxy to find it
# Leave blank if not yet known; those endpoints will return 503
STATS_BASE: str | None = os.environ.get("STATS_BASE") or None

# GMS_SOURCE_ROOT: root for all source-2669606 endpoints (hero catalog, stats, trends, combos)
# Discovered via Fernet decryption of ridwaanhall/api-mobilelegends security.py
GMS_SOURCE_ROOT: str = os.environ.get(
    "GMS_SOURCE_ROOT",
    "https://api.gms.moontontech.com/api/gms/source/2669606",
)

# GMS_BASE: hero catalog (source 2669606, endpoint 2756564) — no JWT, POST JSON
GMS_BASE: str = f"{GMS_SOURCE_ROOT}/2756564"

# GMS_ACADEMY_ROOT: root for source-2713644 endpoints (equipment catalog, rank tiers, lane stats)
GMS_ACADEMY_ROOT: str = os.environ.get(
    "GMS_ACADEMY_ROOT",
    "https://api.gms.moontontech.com/api/gms/source/2713644",
)

# MLBB header constants
MLBB_ORIGIN = "https://www.mobilelegends.com"
MLBB_REFERER = "https://www.mobilelegends.com/"
MLBB_X_ACTID = "2728785"   # required only for getBaseInfo
MLBB_X_APPID = "2713644"   # required only for getBaseInfo
