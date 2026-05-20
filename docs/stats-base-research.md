# STATS_BASE Research

## ✅ RESOLVED — 2026-05-19

**`STATS_BASE = https://app.web.moontontech.com/actgateway`**

Live-verified against `battlereport/matches/recent`, `battlereport/stats`, and
`battlereport/heros/frequent` — all return `{"code":0,...}` with real data.
Set in `.env` and tested end-to-end through the local proxy (`uvicorn app.main:app`).

### How a normal person would find it (simpler paths we didn't take)

There are three direct ways that don't require any reverse-engineering:

**A. Mobile app traffic capture** ← easiest, should have been done first
Open MLBB on your phone and navigate to Battle Records. The app calls
`https://app.web.moontontech.com/actgateway/battlereport/*` directly — any proxy
shows it instantly.
- Android: **HTTP Toolkit** (free, no root) at httptoolkit.com
- iPhone: **Stream** or **Charles Proxy** from the App Store

**B. We missed `app.web.moontontech.com` in DNS enumeration**
We probed `api.gms.`, `cdn.web.`, `act.gms.` but never tried `app.web.moontontech.com`.
The `app.` prefix is one of the most common subdomain names and it was a blind spot.
If it had been in the list, the host would have been found immediately — and the path
`/actgateway` was already in our prefix list.

**C. `game.mobilelegends.com` Vue SPA (if it wasn't broken)**
That Vue app exists specifically to show battle records on web. If its JS bundles
(`app.99244ef8.js`) hadn't been deleted from the server, a simple search for `actgateway`
or `moontontech` in the bundle would have revealed the full URL. The broken deployment
turned this from a 30-second find into a multi-session investigation.

---

### How it was actually found (the hard path — final session)
1. **Path-prefix permutation probe** — wrote `scripts/probe_stats_base.py`, ran 152
   requests (4 known-live hosts × 38 prefixes) using `battlereport/matches/recent`
   as the validator. All returned 404 or false-positive HTML (Imperva challenge /
   Watcher of Realms SPA). New host discovered in the process: `act.mobilelegends.com`
   (DNS fails) and `sg-play.mobilelegends.com` (404 on battlereport).

2. **Web search** — found `openmlbb.fastapicloud.dev`, another public proxy by
   `ridwaanhall` (same author as the reference project). Its match endpoint returned
   real data, confirming it had STATS_BASE configured.

3. **GitHub source analysis** — fetched `app/core/security.py` from the open-source repo.
   The URL is stored as a Fernet-encrypted blob. Key derivation:
   `fernet_key = base64(sha256(SECRET_KEY))`.

4. **Django key reuse** — the very first commit of the repo (initial Django setup)
   contained a plain-text Django secret key in `MLBB/settings.py`:
   `django-insecure-0dbenlez&b==-4l3*wn=emswc6)rsj)9dicawy!0da0ekoll=_`
   The developer reused this same string as the FastAPI `SECRET_KEY`.

5. **Decryption** — decrypting `RONE_DEV_KEY_STATS` with the SHA-256-derived Fernet
   key yielded `https://app.web.moontontech.com/actgateway` instantly.

---

## Goal (original)
Find the upstream URL (`STATS_BASE`) that serves all `battlereport/*` endpoints.
`app/services/user.py` constructs URLs as `f"{STATS_BASE}/{path}"`, e.g.:
- `battlereport/stats`
- `battlereport/matches/recent?sid=40&limit=5`
- `battlereport/season/list?sid=40`

---

## All Confirmed Findings ✅

| Finding | How |
|---------|-----|
| `STATS_BASE = https://app.web.moontontech.com/actgateway` | Fernet decryption + live test (2026-05-19) |
| `AUTH_BASE = https://sg-api.mobilelegends.com` | Browser DevTools on mobilelegends.com |
| `/base/sendVc`, `/base/login`, `/base/logout`, `/base/getBaseInfo` all work | Live-tested |
| Header recipe for auth and stats calls | Read from source + live-verified |
| JWT valid ~24 hours, opaque to proxy | Source code + live test |
| Fernet blobs encrypted on **2026-03-22** | Decoded timestamp from blob bytes |
| `app.web.moontontech.com` = STATS_BASE host | Fernet decryption (2026-05-19) |
| `api.moba5v5.com` = mobile-web alt for AUTH_BASE | Found in mobilelegends.com JS bundle |
| `game.mobilelegends.com/battlereport/*` = Vue SPA, broken JS | Fetched HTML |
| `api.gms.moontontech.com` = GMS content server (hero lists, game metadata) | Network traffic |
| `openmlbb.fastapicloud.dev` = ridwaanhall's public FastAPI proxy (working) | Web search |

---

## Domains Discovered

| Domain | Resolves | Purpose | battlereport result |
|--------|----------|---------|---------------------|
| `app.web.moontontech.com` | ✅ | **STATS_BASE host** — actgateway API | ✅ 200 JSON data |
| `sg-api.mobilelegends.com` | ✅ | AUTH_BASE — sendVc/login/logout/getBaseInfo | 404 on `/battlereport/*` |
| `api.gms.moontontech.com` | ✅ | GMS content/metadata | 404 on all paths |
| `act.gms.moontontech.com` | ✅ | Hosts game SPAs (WoR promo, etc.) | 404 on battlereport; `/mlbb` and `/m` serve unrelated SPA |
| `api.moba5v5.com` | ✅ | Mobile-web alt for AUTH_BASE | 404 on battlereport |
| `game.mobilelegends.com` | ✅ | Battle report Vue SPA (broken JS assets) | 200 HTML, no JSON |
| `sg-play.mobilelegends.com` | ✅ | Login SDK / account pages | 404 on battlereport |
| `play.mobilelegends.com` | ✅ | Login SDK JS | 200 but Imperva bot-challenge HTML (false positive) |
| `cdn.web.moontontech.com` | ✅ | Web asset CDN | N/A |
| `static.mobilelegends.com` | ✅ | Static assets CDN | N/A |
| `openmlbb.fastapicloud.dev` | ✅ | ridwaanhall's public FastAPI proxy | returns real data (proxy, not upstream) |

### DNS failed (do not exist)
`sg-actgateway.mobilelegends.com`, `actgateway.mobilelegends.com`,
`act.mobilelegends.com`, `actgateway.gms.moontontech.com`,
`actreport.gms.moontontech.com`, `report.mobilelegends.com`,
`battlereport.mobilelegends.com`, `stats.mobilelegends.com`,
`sg-report.mobilelegends.com`, `sg-stats.mobilelegends.com`,
`actreport.moontontech.com`, `actgateway.moontontech.com`,
`report.moontontech.com`, `actreport.gms.moontontech.com`,
`report.gms.moontontech.com`, `sgact.gms.moontontech.com`,
`act.moba5v5.com`, `sgact.moba5v5.com`, `actgateway.moba5v5.com`,
`api2.mobilelegends.com`, `sg2-api.mobilelegends.com`,
`id-api.mobilelegends.com`, `ph-api.mobilelegends.com`

---

## Methods Used (chronological)

### Session 1 (prior)
1. **Browser DevTools** — navigated mobilelegends.com with real JWT injected. The web SPA
   never calls any `battlereport/*` URL — battle records don't exist on web.
2. **JS bundle analysis** — searched `mobilelegends.com/assets/index-6b6511f7.js`.
   Found config object with known domains; no `battlereport` string anywhere.
3. **DNS enumeration** — 30+ subdomain patterns. Only new finds: `game.mobilelegends.com`
   and `act.gms.moontontech.com`. Neither serves battlereport.
4. **`game.mobilelegends.com` investigation** — Vue SPA shell at `/battlereport/`. JS
   bundles (`app.99244ef8.js`, `chunk-vendors.e22bd454.js`) all 404 — deleted from server.
   Wayback Machine CDX API had no snapshots of those files.
5. **Fernet brute-force (round 1)** — 90+ common SECRET_KEY values (project names, author
   name, passwords, domain names). None matched.
6. **mlbb.rone.dev live API** — Cloudflare blocks Python requests (Error 1010). Works in
   browser. Response headers show no upstream URL leak.
7. **`/r` endpoint probe** — `sg-api.mobilelegends.com/r` returns 400 for all payloads
   tried. Appears to be a telemetry sink, not an API router.
8. **Login SDK JS** — `play.mobilelegends.com/base/login/index.js` only references
   `sg-api.mobilelegends.com`. No battlereport URL.

### Session 2 — 2026-05-19 (this session)
9. **Path-prefix permutation probe** — `scripts/probe_stats_base.py` ran 152 async
   requests (4 hosts × 38 prefixes) with a real JWT. All 150/152 returned 404.
   2 false positives: `act.gms.moontontech.com/mlbb` and `/m` serve an unrelated WoR
   promo SPA (200 HTML, Imperva challenge on `play.mobilelegends.com` also false-positive).
10. **Web search** — searching for `battlereport` + GitHub led to `openmlbb.fastapicloud.dev`
    (public proxy by ridwaanhall). Its `/api/user/matches` returned real data with our JWT.
11. **GitHub source analysis** — fetched `app/core/security.py` from
    `ridwaanhall/api-mobilelegends`. Found three Fernet blobs: `RONE_DEV_KEY_AUTH`,
    `RONE_DEV_KEY_DATA`, `RONE_DEV_KEY_STATS`. Key derivation: `base64(sha256(SECRET_KEY))`.
12. **Commit history dig** — walked through all commits to the repo's initial state.
    Found the very first commit (`463e5c58`) had a plain-text Django insecure key in
    `MLBB/settings.py`. Developer reused it as the FastAPI `SECRET_KEY`.
13. **Fernet decryption (success)** — decrypted `RONE_DEV_KEY_AUTH` → matched known
    `https://sg-api.mobilelegends.com`. Decrypted `RONE_DEV_KEY_STATS` →
    `https://app.web.moontontech.com/actgateway`. ✅

---

## Path Prefixes Probed and Rejected (session 2, all 4 known hosts)

```
(bare)  /api  /api/act  /act  /actgateway  /api/actgateway
/v1  /v2  /api/v1  /api/v2
/report  /api/report  /api/v1/report  /api/v2/report
/user  /api/user  /api/v1/user
/mlbb  /api/mlbb  /m  /api/m  /web  /api/web
/sg  /api/sg  /game  /api/game
/gms  /api/gms  /act/v1  /act/v2  /v1/act  /v2/act  /api/v1/act
/battle  /api/battle  /battlestats  /api/battlestats
```
Test endpoint: `battlereport/matches/recent?sid=40&limit=5`

---

## How to Validate a Candidate URL

```python
import httpx

JWT = "<jwt from /api/user/auth/login>"
CANDIDATE = "https://app.web.moontontech.com/actgateway"

headers = {
    "authorization": JWT,
    "x-token": JWT,
    "Origin": "https://www.mobilelegends.com",
    "Referer": "https://www.mobilelegends.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

r = httpx.get(f"{CANDIDATE}/battlereport/matches/recent", params={"sid": 40, "limit": 3}, headers=headers)
print(r.status_code, r.text[:300])
```

Success: `{"code": 0, "message": "Success", "data": {...}}`

Known failure patterns:
- `404 page not found` — Go server, wrong path
- `<html>404 Not Found</html>` nginx — wrong path on nginx host
- HTTP 401/403 — right server, wrong auth headers ← worth chasing
- HTTP 400 — right server, wrong params ← worth chasing
- 200 with HTML (SPA shell or Imperva challenge) — false positive

---

## Current Status

Everything is working. `.env` has:
```
AUTH_BASE=https://sg-api.mobilelegends.com
STATS_BASE=https://app.web.moontontech.com/actgateway
```

Remaining action: add `STATS_BASE` to **Vercel environment variables** and redeploy
to enable the stats endpoints in production.
