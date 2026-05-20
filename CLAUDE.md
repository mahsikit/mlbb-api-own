# MLBB API — Own Version

## What this is
A personal FastAPI proxy for the Mobile Legends: Bang Bang player API.
It relays auth and stats requests to Moonton's upstream servers, adding proper
headers so Moonton accepts the requests.

## Project structure
```
app/
  core/config.py      – env var loading (AUTH_BASE, STATS_BASE)
  core/http.py        – header builder + httpx wrappers
  schemas/user.py     – Pydantic request models
  services/user.py    – upstream call functions
  api/deps.py         – JWT extraction dependency
  api/routers/user.py – all API endpoints
  main.py             – FastAPI app + CORS
prod/index.py         – Vercel ASGI entry point
vercel.json           – Vercel build config
requirements.txt
.env.example
docs/
  context.md          – upstream API internals (how Moonton's API works)
  deployment.md       – Vercel + GitHub deploy guide
```

## Environment variables
| Variable    | Required | Default                                                        | Notes |
|-------------|----------|----------------------------------------------------------------|-------|
| `AUTH_BASE` | No       | `https://sg-api.mobilelegends.com`                             | Confirmed correct |
| `STATS_BASE`| No       | `https://app.web.moontontech.com/actgateway`                   | Confirmed 2026-05-19 — set this in .env |
| `GMS_BASE`  | No       | `https://api.gms.moontontech.com/api/gms/source/2669606/2756564` | Hero catalog — confirmed 2026-05-19 |

## Endpoints
### Always available (no STATS_BASE needed)
| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| GET  | `/api/user/ip` | — | Caller IP geolocation: city, state, country, lang (no auth) |
| GET  | `/api/user/server-config` | — | Moonton server time + captcha version (no auth) |
| GET  | `/api/user/heroes/catalog` | — | All 132 heroes: name, role, lane, difficulty, portrait (no auth) |
| GET  | `/api/user/heroes/stats` | `window=7d` (1d/3d/7d/15d/30d) | Hero win/pick/ban rates by time window (no auth) |
| GET  | `/api/user/heroes/combos` | — | Curated hero skill combo guides (no auth) |
| GET  | `/api/user/heroes/trends` | `window=7d` (7d/15d/30d) | Daily win-rate trend per hero (no auth) |
| GET  | `/api/user/heroes/stats/by-lane` | — | Hero win rate by lane and rank tier (no auth) |
| GET  | `/api/user/catalog/equipment` | — | 184 items: id, name, icon URL — resolves item IDs in match builds (no auth) |
| GET  | `/api/user/catalog/ranks` | — | bigrank 1–7 → tier names (Warrior→Mythic) + sub-rank icons (no auth) |
| GET  | `/api/user/rankings` | — | Active hero rating polls index (no auth) |
| GET  | `/api/user/rankings/{subject_id}` | — | Ranked hero list for a rating poll subject (no auth) |
| POST | `/api/user/auth/send-vc` | `{role_id, zone_id}` | Triggers 4-digit VC to in-game mail |
| POST | `/api/user/auth/login` | `{role_id, zone_id, vc}` | Returns JWT + token |
| POST | `/api/user/auth/logout` | `{role_id, zone_id}` + Bearer JWT | Invalidates JWT |
| POST | `/api/user/info` | `{role_id, zone_id}` + Bearer JWT | Avatar, level, name, rank_level, reg_country |
| POST | `/api/user/friends/basic` | `{role_id, zone_id}` + Bearer JWT | Friends with name + avatar. **Cross-player:** pass target's role_id/zone_id to get their friend list (72+ friends with display names). |

### Requires STATS_BASE (returns 503 until configured)

> **Cross-player lookup:** endpoints marked with `*` accept optional `?rid=<Game ID>&zid=<Server ID>` query params to look up **any player's** data. Omit them to get your own data (JWT owner).

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| GET | `/api/user/stats` * | Bearer JWT | Career totals: wins, games, avg score, records |
| GET | `/api/user/season` | `sid` + Bearer JWT | Available season IDs |
| GET | `/api/user/matches` * | `sid`, `limit`, `last_cursor` + Bearer JWT | Recent matches (paginated) |
| GET | `/api/user/matches/{match_id}` | `sid` + Bearer JWT | Match detail — all 10 players, items, KDA. Works for **any** bid in the system (not just your own matches). |
| GET | `/api/user/matches/mode/{mode}` * | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Matches by game mode: classic/arcade/brawl/tournament/vs/custom |
| GET | `/api/user/matches/stub/{name}` | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Stub match endpoints (registered upstream, return `[]` today) |
| GET | `/api/user/heroes/frequent` * | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Most-played heroes (paginated) |
| GET | `/api/user/heroes/{hero_id}/matches` * | `sid`, `limit`, `last_cursor` + Bearer JWT | Matches played with a specific hero |
| GET | `/api/user/friends` * | `sid`(opt) + Bearer JWT | Friend list with co-op win rates (STATS_BASE) |
| GET | `/api/user/privacy/settings` * | Bearer JWT | Privacy state — use to check if a player is public |
| POST | `/api/user/privacy/settings` | `{"visible": true/false}` + Bearer JWT | Toggle your own profile visibility |

## Local dev
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env if needed
uvicorn app.main:app --reload
# open http://localhost:8000/docs
```

## Deploy to Vercel
See docs/deployment.md for step-by-step instructions.

## How login works
1. Player sends `role_id` (Game ID) + `zone_id` (Server ID)
2. Moonton sends a 4-digit code to the player's in-game mail (5 min TTL)
3. Player sends `role_id` + `zone_id` + `vc` (the code)
4. Moonton returns a JWT (~24 hours valid)
5. All subsequent calls use `Authorization: Bearer <jwt>`

The JWT is issued by Moonton. This server never generates or validates it —
it only forwards it in headers and lets Moonton's servers check it.
