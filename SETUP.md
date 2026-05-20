# MLBB API Own — Setup & Deployment Guide

## What this project is

A FastAPI proxy that talks directly to Moonton's upstream servers:
- `sg-api.mobilelegends.com` — auth (send-vc, login, getBaseInfo)
- `app.web.moontontech.com/actgateway` — player stats, matches, frequent heroes
- `api.gms.moontontech.com` — public hero catalog, win/pick/ban rates

This replaces the third-party `mlbb.rone.dev` dependency used by the Next.js app
at `~/Documents/mlbb-layer`. Once deployed, `mlbb-layer` points its `MLBB_API_BASE`
env var at this project's Vercel URL.

---

## Step 1 — Push to GitHub

```bash
cd ~/Downloads/mlbb-api-own

git init
git add .
git commit -m "initial: mlbb api proxy"
```

Then create a **new empty repo** on github.com (do NOT initialize with README/license),
copy the remote URL it gives you, and:

```bash
git remote add origin https://github.com/YOUR_USERNAME/mlbb-api-own.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Deploy to Vercel

1. Go to **https://vercel.com/new**
2. Click **Import Git Repository** → select `mlbb-api-own`
3. Framework preset: **Other** (not Next.js, not Python — leave as Other)
4. Root directory: leave as `/` (default)
5. Build & output settings: leave all as default (Vercel reads `vercel.json`)
6. Click **Environment Variables** and add:

| Name | Value | Required |
|------|-------|----------|
| `STATS_BASE` | `https://app.web.moontontech.com/actgateway` | **Yes — mandatory** |
| `AUTH_BASE` | `https://sg-api.mobilelegends.com` | No (has default) |
| `GMS_SOURCE_ROOT` | `https://api.gms.moontontech.com/api/gms/source/2669606` | No (has default) |
| `GMS_ACADEMY_ROOT` | `https://api.gms.moontontech.com/api/gms/source/2713644` | No (has default) |

> ⚠️ `STATS_BASE` is mandatory. Without it every `/stats`, `/matches`, `/season`,
> `/heroes/frequent` endpoint returns HTTP 503 — which breaks the entire profile page
> in `mlbb-layer`.

7. Click **Deploy**

---

## Step 3 — Smoke test the live deployment

Once Vercel finishes deploying, your API is at `https://YOUR-PROJECT.vercel.app`.

Open the interactive docs at: `https://YOUR-PROJECT.vercel.app/docs`

Run these checks in order:

```bash
BASE=https://YOUR-PROJECT.vercel.app

# 1. Health check
curl $BASE/

# 2. Public hero catalog (no auth)
curl "$BASE/api/user/heroes/catalog" | python3 -m json.tool | head -20

# 3. Hero win/pick/ban rates (no auth — proves GMS works)
curl "$BASE/api/user/heroes/stats?window=7d" | python3 -m json.tool | head -20

# 4. Send OTP to your in-game mail (replace with your Game ID / Server ID)
curl -X POST "$BASE/api/user/auth/send-vc" \
  -H "Content-Type: application/json" \
  -d '{"role_id": YOUR_ROLE_ID, "zone_id": YOUR_ZONE_ID}'
# Expected: {"code": 0, "data": "", "msg": "ok"}

# 5. Login with the code from in-game mail
curl -X POST "$BASE/api/user/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"role_id": YOUR_ROLE_ID, "zone_id": YOUR_ZONE_ID, "vc": "1234"}'
# Expected: {"code": 0, "data": {"jwt": "eyJ...", "token": "...", ...}}

# Save the jwt from step 5, then:
JWT=eyJ...

# 6. Get your profile (proves AUTH_BASE works)
curl -X POST "$BASE/api/user/info" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"role_id": YOUR_ROLE_ID, "zone_id": YOUR_ZONE_ID}'
# Expected: {"code": 0, "data": {"name": "...", "rank_level": ..., "avatar": "..."}}

# 7. Get recent matches (proves STATS_BASE works — most important check)
curl "$BASE/api/user/matches?sid=40&limit=5" \
  -H "Authorization: Bearer $JWT"
# Expected: {"code": 0, "data": {"result": [...matches...], "pageInfo": {...}}}
```

If step 7 returns `{"detail": "STATS_BASE not configured"}` — go to Vercel →
your project → Settings → Environment Variables → add `STATS_BASE` → Redeploy.

---

## Step 4 — Wire the deployed URL into mlbb-layer

Once all smoke tests pass, go to **`~/Documents/mlbb-layer`** and:

### In `.env.local`
```
MLBB_API_BASE=https://YOUR-PROJECT.vercel.app/api/user
```

### In Vercel (mlbb-layer project)
Go to the `mlbb-layer` Vercel project → Settings → Environment Variables → add:
```
MLBB_API_BASE = https://YOUR-PROJECT.vercel.app/api/user
```
Then trigger a redeploy of `mlbb-layer`.

---

## How mlbb-layer uses this API

Every call that used to go to `https://mlbb.rone.dev/api/user/...` now goes to your
Vercel URL instead. The code changes are already in `mlbb-layer` — only the env var
needs to be set.

Key contract notes (already handled in mlbb-layer code):
- `/info` is a **POST** with body `{"role_id": ..., "zone_id": ...}` + Bearer JWT.
  rone.dev was GET + Bearer only. mlbb-layer now extracts role/zone from the JWT and POSTs.
- All other endpoints (stats, season, matches, frequent heroes) are GET + Bearer. Same shape.
- Response envelopes match: `{code, data, msg}` with identical field names (`wc`, `tc`,
  `hid`, `k`, `d`, `a`, `bid`, `mvp`, `res`, `hid_e`, `rank_level`, `roleId`, etc.)

---

## API endpoint reference

See `CLAUDE.md` for the full endpoint table and `docs/context.md` for upstream internals.

### No-auth endpoints (always work)
- `GET /api/user/heroes/catalog` — all 132 heroes
- `GET /api/user/heroes/stats?window=7d` — win/pick/ban rates (1d/3d/7d/15d/30d)
- `GET /api/user/heroes/stats/by-lane` — per-hero win rate by lane and rank tier
- `GET /api/user/heroes/trends?window=7d` — daily trend time series
- `GET /api/user/catalog/equipment` — 184 items with icons (resolves match build item IDs)
- `GET /api/user/catalog/ranks` — bigrank tier names and icons
- `GET /api/user/server-config` — Moonton server time

### Auth endpoints (require Bearer JWT from login)
- `POST /api/user/auth/send-vc` — trigger OTP to in-game mail
- `POST /api/user/auth/login` — exchange OTP for JWT
- `POST /api/user/info` + `{role_id, zone_id}` — player profile
- `GET  /api/user/stats` — career totals
- `GET  /api/user/season?sid=40` — available season IDs
- `GET  /api/user/matches?sid=40&limit=10` — recent matches
- `GET  /api/user/matches/{bid}?sid=40` — match detail (all 10 players)
- `GET  /api/user/heroes/frequent?sid=40&limit=15` — most-played heroes
- `GET  /api/user/friends` — co-op friend stats (adds name/avatar vs co-op rates)

---

## Local dev

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set STATS_BASE=https://app.web.moontontech.com/actgateway
uvicorn app.main:app --reload
# Open http://localhost:8000/docs
```

---

## Vercel timeout note

Vercel free tier has a **10-second serverless function timeout**. The httpx client timeout
in `app/core/http.py` is already set to 8s so upstream failures surface before Vercel
kills the request with a generic 504. Cold starts add ~500ms on the first request after idle.
