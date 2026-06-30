# Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---


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
| GET  | `/api/user/heroes/stats` | `window=7d` (1d/3d/7d/15d/30d), `bigrank=7` (7=Mythic, 8=Honor, 9=Glory) | Hero win/pick/ban rates by time window and rank tier (no auth) |
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
| POST | `/api/user/friends/basic` | `{role_id, zone_id}` + Bearer JWT | Your own friends with name + avatar. Body params are ignored by upstream — always returns JWT owner's friend list. |

### Requires STATS_BASE (returns 503 until configured)

> **Cross-player lookup does NOT exist.** All STATS_BASE and AUTH_BASE endpoints identify the player from the JWT (`Ext.roleId` / `Ext.zoneId`). Any `rid`/`zid` query params are silently ignored by upstream. The `?rid=&zid=` params and `_inject_target()` in `services/user.py` are dead code — confirmed 2026-05-28.
>
> The one exception: `matches/{match_id}` is a **true global lookup** — it returns all 10 players for any match ID in the system regardless of who the JWT belongs to.

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| GET | `/api/user/stats` | Bearer JWT | Career totals: wins, games, avg score, records |
| GET | `/api/user/season` | `sid` + Bearer JWT | Available season IDs |
| GET | `/api/user/matches` | `sid`, `limit`, `last_cursor` + Bearer JWT | Recent matches (paginated) |
| GET | `/api/user/matches/{match_id}` | `sid` + Bearer JWT | Match detail — all 10 players, items, KDA. **Global**: works for any bid in the system, not just your own matches. Returns `rid`, `zid`, `rname` for every player. |
| GET | `/api/user/matches/mode/{mode}` | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Matches by game mode: classic/arcade/brawl/tournament/vs/custom |
| GET | `/api/user/matches/stub/{name}` | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Stub match endpoints (registered upstream, return `[]` today) |
| GET | `/api/user/heroes/frequent` | `sid`(opt), `limit`, `last_cursor` + Bearer JWT | Most-played heroes (paginated) |
| GET | `/api/user/heroes/{hero_id}/matches` | `sid`, `limit`, `last_cursor` + Bearer JWT | Matches played with a specific hero |
| GET | `/api/user/friends` | `sid`(opt) + Bearer JWT | Co-op friend stats: best friend, top win-rate friend, all co-op partners with games/wins/coop level |
| GET | `/api/user/privacy/settings` | Bearer JWT | Your own privacy state |
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

JWT TTL is **7 days** (not 24 hours as originally assumed) — confirmed from `exp` field 2026-05-28.

---

## Pen-test findings (2026-05-28)

### Cross-player lookup — does not exist
Tested every plausible param name (`rid`, `zid`, `roleId`, `zoneId`, `role_id`, `zone_id`, `uid`),
every HTTP method (GET query string, POST form body, POST JSON body), mobile User-Agent,
and ~60 guessed endpoint names across AUTH_BASE and STATS_BASE. All return the JWT owner's
own data. Moonton reads player identity exclusively from `Ext.roleId`/`Ext.zoneId` inside the JWT.

**Tested params that are all ignored:**
- `?rid=X&zid=Y` (current code in `_inject_target`)
- `?roleId=X&zoneId=Y`
- POST body `{"roleId": X, "zoneId": Y}`

### match/{bid} is a true global endpoint
`GET /api/user/matches/{match_id}?sid=N` returns all 10 players for **any** match in the system —
including players the JWT owner has never played with. Returns full `rid`, `zid`, `rname`, KDA,
item builds, damage share, gold for each player. This is the only way to get data on another player,
but requires knowing a match ID they participated in.

### Moonton infrastructure map (confirmed)
| Domain | Role |
|--------|------|
| `sg-api.mobilelegends.com` | AUTH_BASE — login, profile, friend list |
| `app.web.moontontech.com/actgateway` | STATS_BASE — battle report, match history |
| `api.gms.moontontech.com` | GMS — hero catalog, game content |
| `sharepage.mobilelegends.com` | Share page — validates `r_url` domain whitelist then redirects |
| `new.mobilelegends.com` | Web SPA — no cross-player API; web app config only has `api = sg-api` |
| `api.moba5v5.com` | Mirror of AUTH_BASE (India region) |
| `cdn.web.moontontech.com` | CDN for web assets |

### WAF behaviour
The actgateway is behind **Alibaba Cloud WAF**. Sending many requests in a short window triggers
a 405 IP block that lasts ~15–60 minutes. Keep requests slow and spaced to avoid triggering it.
Do not run bulk probes or polling loops against upstream.

### Dead code to clean up
- `_inject_target()` in `app/services/user.py` — adds `rid`/`zid` params that upstream ignores
- All `rid: int | None` / `zid: int | None` params on every router endpoint in `app/api/routers/user.py`
- Cross-player note on `POST /api/user/friends/basic` — body params are ignored, always returns self

### Endpoints not yet fully explored (safe to test one at a time)
- `battlereport/friends` — co-op partner stats structure (bfs/wfs/fs fields)
- `battlereport/heros/frequent` with explicit `sid` values
- Full match detail item build resolution (`its_e` array)
- `hero/{hid}/matches` — per-hero match history
- Match pagination cursor flow
- Match modes: classic, brawl, arcade, vs, tournament
