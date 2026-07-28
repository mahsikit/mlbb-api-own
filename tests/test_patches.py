from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import patches
from app.services.patches import (
    PATCH_TITLE_RE,
    extract_hero_changes,
    html_to_lines,
    normalize_patch_record,
)


PATCH_BODY = """
<div><strong>From the Designers</strong></div>
<div>We improved traditional Roamers &amp; jungle pacing.</div>
<div><strong>1. New Hero</strong></div>
<div>New Hero: Example</div>
<div><strong>2. Hero Adjustments</strong></div>
<div>[Saber] (↑)</div>
<div>Saber now has better sustained damage.</div>
<div>[Attributes] (↑)</div>
<div>Base HP: 2440 &gt;&gt; 2500</div>
<div>[Marcel] (~)</div>
<div>Reduced excessive control while improving durability.</div>
<div>[Skill 1] (↓)</div>
<div>Removed the immobilize effect.</div>
<div>[Zhuxin] (↓)</div>
<div>Increased Skill 2's Mana Cost.</div>
<div><strong>3. Battlefield Adjustment</strong></div>
<div>Control Optimizations</div>
"""


class PatchParserTests(unittest.TestCase):
    def setUp(self) -> None:
        patches._cache.clear()
        patches._last_known_good.clear()

    def test_only_accepts_full_patch_note_titles(self) -> None:
        self.assertIsNotNone(PATCH_TITLE_RE.match("2.1.88 PATCH NOTES"))
        self.assertIsNone(PATCH_TITLE_RE.match("PROJECT NEXT Patch Preview"))
        self.assertIsNone(PATCH_TITLE_RE.match("Patch Update Overview"))

    def test_html_to_lines_handles_nested_markup_and_entities(self) -> None:
        lines = html_to_lines("<div>Hello <strong>world</strong> &amp; friends</div>")
        self.assertEqual(lines, ["Hello world & friends"])

    def test_extracts_hero_changes_without_skill_headings_as_heroes(self) -> None:
        changes = extract_hero_changes(html_to_lines(PATCH_BODY))
        self.assertEqual([item["hero_name"] for item in changes], ["Saber", "Marcel", "Zhuxin"])
        self.assertEqual(
            [item["direction"] for item in changes],
            ["buff", "adjustment", "nerf"],
        )
        self.assertIn("[Attributes] (↑)", changes[0]["details"])
        self.assertIn("[Skill 1] (↓)", changes[1]["details"])

    def test_normalizes_article_without_returning_html(self) -> None:
        result = normalize_patch_record(
            {
                "id": 3314600,
                "data": {
                    "title": "2.1.88 PATCH NOTES",
                    "start_time": 1781683210000,
                    "cover": "https://example.com/cover.jpg",
                    "body": PATCH_BODY,
                },
            },
            include_details=True,
        )
        self.assertEqual(result["version"], "2.1.88")
        self.assertEqual(result["news_id"], 3314600)
        self.assertEqual(result["designer_summary"], ["We improved traditional Roamers & jungle pacing."])
        self.assertEqual(result["battlefield_summary"], ["Control Optimizations"])
        self.assertNotIn("body", result)

    @patch("app.services.patches._fetch_records")
    def test_patch_list_filters_non_patch_articles(self, fetch_records) -> None:
        fetch_records.return_value = [
            {"id": 10, "data": {"title": "PROJECT NEXT Preview"}},
            {
                "id": 11,
                "data": {
                    "title": "2.1.88 PATCH NOTES",
                    "start_time": 1781683210000,
                    "cover": None,
                },
            },
        ]
        result = patches.get_patch_list(10)
        self.assertEqual([item["version"] for item in result], ["2.1.88"])

    @patch("app.services.patches._fetch_records")
    def test_uses_last_known_good_after_upstream_failure(self, fetch_records) -> None:
        fetch_records.return_value = [
            {
                "id": 11,
                "data": {
                    "title": "2.1.88 PATCH NOTES",
                    "start_time": 1781683210000,
                    "cover": None,
                },
            }
        ]
        expected = patches.get_patch_list(1)
        patches._cache.clear()
        fetch_records.side_effect = TimeoutError("upstream timed out")
        self.assertEqual(patches.get_patch_list(1), expected)


if __name__ == "__main__":
    unittest.main()
