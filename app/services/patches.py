from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from threading import Lock
from time import monotonic
from typing import Any

from app.core.config import GMS_SOURCE_ROOT
from app.core.http import post_json_public

PATCH_SOURCE_ID = "2672947"
PATCH_CHANNEL_ID = 2678956
# An article is patch notes when its title ends in "PATCH NOTES". The version is
# whatever precedes that, but it is not always usable: Moonton ships titles with
# the version truncated (news 3503357 is "16 PATCH NOTES", for patch 2.2.16) and
# occasionally omits it entirely. Requiring a full version here dropped those
# articles outright, so callers get version=None and resolve it from a patch
# calendar of their own instead.
PATCH_TITLE_RE = re.compile(
    r"^\s*(?P<version>\S*)\s*PATCH\s+NOTES\s*$",
    re.IGNORECASE,
)
# Hotfixes carry a letter suffix, e.g. "2.1.95a".
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+[A-Za-z]?$")
CHANGE_HEADING_RE = re.compile(r"^\[([^\]]+)\]\s*\(([↑↓~])\)\s*$")
NUMBERED_SECTION_RE = re.compile(r"^\d+\.\s+")

_DIRECTION = {"↑": "buff", "↓": "nerf", "~": "adjustment"}
_NON_HERO_HEADINGS = {
    "attribute",
    "attributes",
    "passive",
    "ultimate",
}
_CACHE_TTL_SECONDS = 15 * 60
_cache_lock = Lock()
_cache: dict[str, tuple[float, Any]] = {}
_last_known_good: dict[str, Any] = {}


class _BlockTextParser(HTMLParser):
    """Convert rich-text HTML into readable lines without returning HTML."""

    _BLOCK_TAGS = {
        "div",
        "p",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "br",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buffer: list[str] = []
        self.lines: list[str] = []

    def _flush(self) -> None:
        text = " ".join("".join(self._buffer).replace("\xa0", " ").split())
        self._buffer.clear()
        if text and (not self.lines or self.lines[-1] != text):
            self.lines.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_lines(body: str) -> list[str]:
    parser = _BlockTextParser()
    parser.feed(body or "")
    parser.close()
    return parser.lines


def _is_hero_heading(label: str) -> bool:
    normalized = label.strip().lower()
    if normalized in _NON_HERO_HEADINGS:
        return False
    if normalized.startswith(("skill ", "basic attack", "battle spell")):
        return False
    return True


def _section_slice(lines: list[str], heading: str) -> list[str]:
    start = next(
        (i for i, line in enumerate(lines) if heading.lower() in line.lower()),
        None,
    )
    if start is None:
        return []
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if NUMBERED_SECTION_RE.match(lines[i])
        ),
        len(lines),
    )
    return lines[start + 1 : end]


def extract_hero_changes(lines: list[str]) -> list[dict[str, Any]]:
    adjustment_lines = _section_slice(lines, "Hero Adjustments")
    changes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in adjustment_lines:
        match = CHANGE_HEADING_RE.match(line)
        if match and _is_hero_heading(match.group(1)):
            if current:
                changes.append(current)
            current = {
                "hero_name": match.group(1).strip(),
                "direction": _DIRECTION[match.group(2)],
                "summary": None,
                "details": [],
            }
            continue
        if not current:
            continue
        if current["summary"] is None and not line.startswith("["):
            current["summary"] = line
        else:
            current["details"].append(line)

    if current:
        changes.append(current)
    return changes


def _extract_designer_summary(lines: list[str]) -> list[str]:
    start = next(
        (i for i, line in enumerate(lines) if line.lower() == "from the designers"),
        None,
    )
    if start is None:
        return []
    summary: list[str] = []
    for line in lines[start + 1 :]:
        if NUMBERED_SECTION_RE.match(line):
            break
        summary.append(line)
    return summary


def _extract_battlefield_summary(lines: list[str]) -> list[str]:
    section = _section_slice(lines, "Battlefield Adjustment")
    return section[:20]

def _extract_equipment_summary(lines: list[str]) -> list[str]:
    section = _section_slice(lines, "Equipment Adjustment")
    return section[:20]


def _timestamp_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(
            int(value) / 1000,
            tz=timezone.utc,
        ).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def normalize_patch_record(record: dict[str, Any], *, include_details: bool) -> dict[str, Any]:
    data = record.get("data") or {}
    title = str(data.get("title") or "").strip()
    title_match = PATCH_TITLE_RE.match(title)
    if not title_match:
        raise ValueError(f"Not a patch-notes article: {title!r}")

    version = title_match.group("version")
    news_id = int(record["id"])
    normalized: dict[str, Any] = {
        "version": version if VERSION_RE.match(version) else None,
        "news_id": news_id,
        "title": title,
        "published_at": _timestamp_to_iso(data.get("start_time")),
        "cover_url": data.get("cover"),
        "source_url": (
            "https://www.mobilelegends.com/news/"
            f"articleldetail?newsid={news_id}"
        ),
    }
    if include_details:
        lines = html_to_lines(str(data.get("body") or ""))
        normalized.update(
            {
                "designer_summary": _extract_designer_summary(lines),
                "hero_changes": extract_hero_changes(lines),
                "battlefield_summary": _extract_battlefield_summary(lines),
                "equipment_summary": _extract_equipment_summary(lines),
            }
        )
    if not normalized["published_at"] or not normalized["source_url"]:
        raise ValueError("Patch article is missing required publication metadata")
    return normalized


def _cached(key: str) -> Any | None:
    with _cache_lock:
        item = _cache.get(key)
        if item and monotonic() - item[0] < _CACHE_TTL_SECONDS:
            return item[1]
    return None


def _remember(key: str, value: Any) -> Any:
    with _cache_lock:
        _cache[key] = (monotonic(), value)
        _last_known_good[key] = value
    return value

def _fallback(key: str, error: Exception) -> Any:
    with _cache_lock:
        if key in _last_known_good:
            return _last_known_good[key]
    raise error


def _fetch_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = post_json_public(
        f"{GMS_SOURCE_ROOT}/{PATCH_SOURCE_ID}",
        payload,
    )
    if response.get("code") != 0:
        raise ValueError(f"Unexpected patch source response: {response.get('message')}")
    records = (response.get("data") or {}).get("records")
    if not isinstance(records, list):
        raise ValueError("Patch source response is missing data.records")
    return records


def get_patch_list(limit: int = 20) -> list[dict[str, Any]]:
    cache_key = f"list:{limit}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        records = _fetch_records(
            {
                "pageSize": max(limit * 2, 20),
                "filters": [
                    {
                        "field": "channel",
                        "operator": "hasAnyOf",
                        "value": [PATCH_CHANNEL_ID],
                    },
                    {"field": "title.(i18n)", "operator": "notEmpty"},
                ],
                "sorts": [
                    {
                        "data": {"field": "start_time", "order": "desc"},
                        "type": "sequence",
                    }
                ],
            }
        )
    except Exception as exc:
        return _fallback(cache_key, exc)
    patches = []
    for record in records:
        title = str((record.get("data") or {}).get("title") or "")
        if PATCH_TITLE_RE.match(title):
            patches.append(normalize_patch_record(record, include_details=False))
        if len(patches) >= limit:
            break
    if not patches:
        raise ValueError("Patch source returned no valid patch-notes articles")
    return _remember(cache_key, patches)


def get_latest_patch() -> dict[str, Any]:
    cached = _cached("latest")
    if cached is not None:
        return cached
    latest = get_patch_article(get_patch_list(1)[0]["news_id"])
    return _remember("latest", latest)


def get_patch_article(news_id: int) -> dict[str, Any]:
    cache_key = f"article:{news_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        records = _fetch_records(
            {
                "pageSize": 1,
                "filters": [
                    {"field": "id", "operator": "eq", "value": str(news_id)}
                ],
            }
        )
    except Exception as exc:
        return _fallback(cache_key, exc)
    if not records:
        raise LookupError(f"Patch article {news_id} was not found")
    return _remember(
        cache_key,
        normalize_patch_record(records[0], include_details=True),
    )
