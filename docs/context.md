# MLBB Upstream API — Context & Internals

## The two upstream bases

### AUTH_BASE — `https://sg-api.mobilelegends.com`
**Confirmed.** Found by opening `mobilelegends.com/academy` in Chrome DevTools → Network tab
while logging in. All auth calls go here.

Endpoints:
| Path | Method | Body (form-encoded) | Notes |
|------|--------|---------------------|-------|
| `/c/ip` | GET | (none) | Caller IP geo: `{city, state, country, lang}`. No JWT. |
| `/base/sendVc` | POST | `roleId, zoneId` | Triggers in-game mail code |
| `/base/login` | POST | `roleId, zoneId, vc, referer="academy", type="web"` | Returns JWT |
| `/base/logout` | POST | `roleId, zoneId` + JWT in headers | Invalidates JWT |
| `/base/getBaseInfo` | POST | `roleId, zoneId` + JWT + x-actid + x-appid | Returns profile |
| `/base/getServerConfig` | POST | (empty) | Returns captcha_version + time |
| `/base/getFriendList` | POST | `roleId, zoneId` + JWT + x-actid + x-appid | Full friend list: name, iFaceId, sFacePath. Avatar URL = `https://akmpicture.youngjoygame.com/{sFacePath}` |

### STATS_BASE — `https://app.web.moontontech.com/actgateway`
**Confirmed 2026-05-19.** Found by decrypting the Fernet blob in ridwaanhall's
open-source proxy using the developer's reused Django insecure key.
Set in `.env` as `STATS_BASE=https://app.web.moontontech.com/actgateway`.

#### Live endpoints (return real data)

| Path | Method | Key params | Returns |
|------|--------|------------|---------|
| `battlereport/stats` | GET | — | Career totals: wc, tc, as, gt, mvpc, wsc, mo, hk, ma, ms, mdt, mg, mtd, sids |
| `battlereport/season/list` | GET | — | `sids: [40,39,38,37]` |
| `battlereport/matches/recent` | GET | `sid`, `limit`, `last_cursor` | Paginated match list |
| `battlereport/matches/{bid}` | GET | `sid` | All 10 players in one match |
| `battlereport/heros/frequent` | GET | `sid`, `limit`, `last_cursor` | Most-played heroes, paginated |
| `battlereport/hero/matches` | GET | `hid`, `sid`, `limit`, `last_cursor` | Matches for a specific hero |
| `battlereport/friends` | GET | `sid` | Friend stats: bfs, wfs, fs[] |
| `battlereport/privacy/settings` | GET | — | `{popup_shown, privacy}` |
| `battlereport/privacy/settings` | POST | `privacy=1` (private) / `privacy=2` (visible) | Updated state |

#### Stub endpoints (router-registered, always return `{"result": []}`)

These routes exist in the Go router and respond with `code:0` but never return data.
Likely deprecated features or game modes this account hasn't participated in.

`battlereport/matches/all`, `battlereport/matches/count`, `battlereport/matches/stats`,
`battlereport/matches/win`, `battlereport/matches/lose`, `battlereport/matches/defeat`,
`battlereport/matches/history`, `battlereport/matches/pageInfo`,
`battlereport/matches/summary`

#### Academy endpoints (no JWT required — placeholder works)

| Path | Method | Returns |
|------|--------|---------|
| `academy/rankings` | GET | `{total, list:[{subject, title, desc}]}` — all active hero rating polls |
| `academy/rankings/{subject}` | GET | `{total, list:[{object (hero GMS ID), title, image, image_big}]}` |

Confirmed: these respond with real data even without a valid JWT (auth middleware skips them).

#### Confirmed 404 (not registered)

All paths outside the `battlereport/` prefix return 404 (when JWT is present — see note below), as do:
`battlereport/rank`, `battlereport/achievement`, `battlereport/medal`, `battlereport/mvp`,
`battlereport/guild`, `battlereport/hero/*` (except `hero/matches`),
`battlereport/heros/*` (except `heros/frequent`), `battlereport/friends/*`,
`battlereport/stats/*`, `battlereport/season/*` (except `season/list`)

**Important — middleware false positive:** Without a JWT, the actgateway's global auth
middleware intercepts ALL requests (including 404 paths) and returns HTTP 200 with
`{"code":1002,"message":"auth is empty"}`. This is NOT proof a path is registered.
Always probe with a real JWT to get the true router response.

**How to find STATS_BASE:**
The most reliable way is to capture MLBB mobile app network traffic:
1. Install **Charles Proxy** or **mitmproxy** on your computer
2. Set it as the HTTP proxy on your phone
3. Install the proxy's root certificate on your phone (required for HTTPS)
4. Open the MLBB app and go to your profile / battle records
5. In Charles/mitmproxy, look for requests to a host other than `sg-api.mobilelegends.com`
   that contain paths like `battlereport/stats` — that host is your STATS_BASE

Ruled out candidates (all return 404 for battlereport paths):
- `api.gms.moontontech.com`
- `act.gms.moontontech.com`
- `api.moba5v5.com`
- `game.mobilelegends.com`
- `sg-api.mobilelegends.com` (only works for /base/* not /battlereport/*)

See `docs/stats-base-research.md` for the full discovery story.

### GMS source 2669606 — all confirmed endpoints

Base: `https://api.gms.moontontech.com/api/gms/source/2669606/{endpoint_id}`
Method: POST, body: `{"pageSize": 200}`, no JWT.

| Endpoint ID | Proxy path | Window | Description |
|-------------|-----------|--------|-------------|
| `2756564` | `/heroes/catalog` | — | Hero list: name, role, lane, difficulty, portraits |
| `2756567` | `/heroes/stats?window=1d` | 1 day | Hero win/pick/ban by bigrank+camp_type |
| `2756568` | `/heroes/stats?window=3d` | 3 day | same schema |
| `2756569` | `/heroes/stats?window=7d` | 7 day | same schema |
| `2756565` | `/heroes/stats?window=15d` | 15 day | same schema |
| `2756570` | `/heroes/stats?window=30d` | 30 day | same schema |
| `2674711` | `/heroes/combos` | — | Skill combo guides: caption, desc, hero GMS ID |
| `2674709` | `/heroes/trends?window=7d` | 7 day | Daily win/pick/ban time series per hero |
| `2687909` | `/heroes/trends?window=15d` | 15 day | same schema |
| `2690860` | `/heroes/trends?window=30d` | 30 day | same schema |

**Record structure for hero stats (2756567–70):**
`data.records[].data = {bigrank, camp_type, main_hero: {data: {heroid, name, head, win_rate, pick_rate, ban_rate}}}`
- `bigrank`: "1"=All ranks, "2"=Epic+
- `camp_type`: "0"=Classic, "1"=Ranked

**Record structure for hero trends (2674709, 2687909, 2690860):**
`data.records[].data = {bigrank, camp_type, main_heroid, win_rate: [{date, app_rate, ban_rate, value (win_rate)}]}`

**Record structure for hero combos (2674711):**
`data.records[] = {caption, configId, data: {_object (hero GMS ID), desc (combo steps)}}`

### GMS_BASE — `https://api.gms.moontontech.com/api/gms/source/2669606/2756564`
**Confirmed 2026-05-19.** Found via Fernet decryption of ridwaanhall/api-mobilelegends
`app/core/security.py` using the same Django insecure key that revealed STATS_BASE.
Set in `.env` as `GMS_BASE=https://api.gms.moontontech.com/api/gms/source/2669606/2756564`.

| Path | Method | Body (JSON) | Auth | Returns |
|------|--------|-------------|------|---------|
| *(full URL above)* | POST | `{"pageSize": 200}` | None | 132 heroes: heroid, name, sortlabel (role), roadsortlabel (lane), difficulty, speciality, head/squarehead (portrait URLs) |

The endpoint is a GMS "source" collection. `pageSize: 200` fetches all heroes in one call.
Default without `pageSize` returns 100.

### GMS source 2713644 — academy/catalog endpoints

Base: `https://api.gms.moontontech.com/api/gms/source/2713644/{endpoint_id}`
All confirmed 2026-05-19. Method: POST `{"pageSize": N}`. No JWT required.
Set in `.env` (or config default) as `GMS_ACADEMY_ROOT`.

| Endpoint ID | Proxy path | pageSize | Returns |
|-------------|------------|----------|---------|
| `2775075` | `/catalog/equipment` | 200 | 184 items: `equipid`, `equipname`, `equipicon` (URL) |
| `3210596` | `/catalog/ranks` | 50 | bigrank 1–7 + sub-ranks: names, tier icons, sub-rank icons |
| `2777027` | `/heroes/stats/by-lane` | 200 | Per-hero win rate by lane + rank tier |

**Equipment catalog** (`2775075`):
Fields per record: `equipid` (integer), `equipname` (display name), `equipicon` (icon URL).
Useful for resolving the `its[]` item array in `battlereport/matches/{bid}` to names/icons.

**Rank tier metadata** (`3210596`):
Maps `bigrank` integer IDs → display tier names and sub-rank icons.
`bigrank`: 1=Warrior, 2=Elite, 3=Master, 4=Grandmaster, 5=Epic, 6=Legend, 7=Mythic (incl. Honor/Glory/Immortal).
`bigrank` 101 = aggregate across all ranks. Also referenced in hero stats and lane stats responses.

**Hero win rate by lane and rank** (`2777027`):
Fields: `hero_name`, `real_road` (1=EXP, 2=Gold, 3=Mid, 4=Jungle, 5=Roam),
`big_rank` (5=Epic, 6=Legend, 7=Mythic, 8–9=high Mythic, 101=All),
`total_win_rate`, `time_win_rate`.

---

## Required headers

### For all AUTH_BASE calls
```
Content-Type:  application/x-www-form-urlencoded; charset=UTF-8
User-Agent:    <any real browser UA — rotate to avoid blocks>
Accept:        */*
Origin:        https://www.mobilelegends.com
Referer:       https://www.mobilelegends.com/
DNT:           1
```

### After login (add to the above for getBaseInfo, logout)
```
authorization: <jwt>     (raw, no "Bearer " prefix)
x-token:       <jwt>     (same value)
```

### Only for /base/getBaseInfo
```
x-actid: 2728785
x-appid: 2713644
```

### For STATS_BASE battlereport/* calls
Same auth headers (`authorization`, `x-token`, Origin, Referer, UA) but
`Content-Type` is not set (it's a GET request with query params).

## JWT structure
```json
{
  "exp": 1779220640,
  "Ext": {
    "zoneId": 10382,
    "roleId": 742039794,
    "channel": "web",
    "app_name": "mlbb",
    "token": "...",
    "uid": 8207882,
    "refer": "academy",
    "game_id": 1
  }
}
```
- Valid for ~24 hours from issue
- The server never validates this JWT — it just forwards it to Moonton
- `token` field inside `Ext` is a separate session token (different from the JWT itself)

## Login flow (what happens on each call)

### sendVc
```
POST sg-api.mobilelegends.com/base/sendVc
body: roleId=742039794&zoneId=10382

Response: {"code": 0, "data": "", "msg": "ok"}
```

### login
```
POST sg-api.mobilelegends.com/base/login
body: roleId=742039794&zoneId=10382&vc=2379&referer=academy&type=web

Response: {
  "code": 0,
  "data": {
    "jwt": "eyJhbGciOi...",
    "token": "MTc3...",
    "roleid": 742039794,
    "zoneid": 10382,
    "time": 1779134240
  }
}
```

### getBaseInfo
```
POST sg-api.mobilelegends.com/base/getBaseInfo
headers: authorization=<jwt>, x-token=<jwt>, x-actid=2728785, x-appid=2713644
body: roleId=742039794&zoneId=10382

Response: {
  "code": 0,
  "data": {
    "avatar": "https://akmpicture.youngjoygame.com/...",
    "level": 81,
    "name": "★Yoshino★",
    "rank_level": 172,
    "reg_country": "PH",
    "roleId": 742039794,
    "zoneId": 10382
  }
}
```

## Response field reference

All field names in actgateway responses use short abbreviations. Confirmed meanings:

### `battlereport/stats` fields
| Field | Meaning |
|-------|---------|
| `wc` | Win count (career total) |
| `tc` | Total games played |
| `as` | Average score per game |
| `gt` | Average game time (seconds) |
| `mvpc` | MVP count |
| `wsc` | Win streak count (best ever) |
| `mo` | Most outstanding performance (highest damage dealt in one game) |
| `hk` | Highest kills in one game |
| `ma` | Most assists in one game |
| `ms` | Most score in one game |
| `mdt` | Most damage taken in one game |
| `mg` | Most gold earned in one game |
| `mtd` | Most total damage in one game |
| `sids` | Available season IDs for this account |

Each record stat object (`mo`, `hk`, `ma`, etc.) contains: `v` (value), `ts` (timestamp), `hid` (hero), `bid` (match), `sid`, `hid_e` (hero detail), `bid_s` (match ID as string).

### `battlereport/matches/recent` — per-match fields
| Field | Meaning |
|-------|---------|
| `bid` | Match ID (int64) |
| `bid_s` | Match ID as string (use this for API calls) |
| `hid` | Hero ID played |
| `k` | Kills |
| `d` | Deaths |
| `a` | Assists |
| `lid` | Lane ID (1=EXP, 2=Gold/Marksman, 3=Mid, 4=Jungle, 5=Roam) |
| `s` | Score |
| `mvp` | 1=MVP, 0=not |
| `res` | Result: 1=win, 0=loss |
| `ts` | Unix timestamp of match end |
| `sid` | Season ID |
| `hid_e` | Hero enriched: `{id, n (name), ix (icon URL), i2x (splash URL)}` |

### `battlereport/matches/{bid}` — per-player fields (10 players total)
| Field | Meaning |
|-------|---------|
| `f` | Faction/team (1 or 2) |
| `hid` | Hero ID |
| `rid` | Player role ID (Game ID) |
| `zid` | Player zone ID (Server ID) |
| `rname` | Player name |
| `k/d/a` | Kills / Deaths / Assists |
| `tfr` | Team fight rate (share of team damage in fights) |
| `o` | Gold earned |
| `op` | Output performance (damage share %) |
| `s` | Score |
| `mvp` | 1=MVP |
| `its` | Item IDs array (6 build slots + 1 spell) |
| `its_e` | Items enriched: `[{id, n, ix}]` |
| `hlvl` | Hero level at match end |
| `bd` | Battle duration (seconds) |
| `fk` | Physical kill contribution |
| `fw` | First blood flag |
| `eq` | Emblem index |
| `ts` | Match timestamp |

### `battlereport/heros/frequent` — per-hero fields
| Field | Meaning |
|-------|---------|
| `hid` | Hero ID |
| `tc` | Total games with this hero |
| `wc` | Wins with this hero |
| `bs` | Best score |
| `mr` | Match rating (performance score) |
| `mrp` | Match rating percentile (0–1) |
| `p` | Points (rank points gained) |
| `hid_e` | Hero enriched detail |

### `battlereport/friends` — structure
```
{
  "bfs": [best friend this season (most games together) — always 1 item],
  "wfs": [win friend this season (highest win rate together) — always 1 item],
  "fs":  [all co-op friends, sorted by cooperation level]
}
```

Per-friend fields:

| Field | Meaning |
|-------|---------|
| `f.n` | Friend's name — empty string when `pri: true` |
| `f.ax` | Friend's avatar URL — empty when `pri: true` |
| `f.pri` | `true` = profile private (name/avatar hidden) |
| `f.rid` / `f.zid` | Always `0` — Moonton never exposes friend role/zone IDs via this endpoint |
| `frid` / `fzid` | Same as `f.rid` / `f.zid`, redundant, always `0` |
| `cl` | Cooperation level — grows the more games you play together |
| `l` | Total score (mirrors or caps `cl`, meaning unclear) |
| `tbc` | Total battles together this season |
| `twc` | Total wins together this season |

Win rate with a friend = `twc / tbc` (e.g. 17/20 = 85%).

### `base/getFriendList` — per-friend fields
| Field | Meaning |
|-------|---------|
| `sName` | Friend's display name |
| `iFaceId` | Avatar frame/icon type ID (integer) |
| `sFacePath` | Relative avatar path — prepend `https://akmpicture.youngjoygame.com/` for full URL. Empty string for some friends. |
| `iRoleId` | Friend's Game ID (hex-encoded, privacy-obfuscated — not a raw integer) |
| `iZoneId` | Friend's Server ID (hex-encoded, privacy-obfuscated) |

Returns all friends (up to 72+ confirmed). No pagination params needed.
Different from `battlereport/friends`: this has names + avatars; that has co-op win-rate stats.

## Known Moonton domains
| Domain | Purpose |
|--------|---------|
| `sg-api.mobilelegends.com` | Auth + base info (AUTH_BASE) |
| `api.gms.moontontech.com` | GMS content/metadata (hero lists, game content) |
| `cdn.web.moontontech.com` | CDN for web assets |
| `static.mobilelegends.com` | Static web resources |
| `play.mobilelegends.com` | Login SDK JS |
| `game.mobilelegends.com` | Battle report web SPA (broken assets as of 2026-03) |
| `api.moba5v5.com` | Alternative API base for mobile web (same as AUTH_BASE) |
| `akmweb.youngjoygame.com` | Hero/player image CDN |
| `akmpicture.youngjoygame.com` | Player avatar CDN |
