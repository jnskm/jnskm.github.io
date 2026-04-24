from __future__ import annotations

from pathlib import Path
import unittest

from site_steward.extractors import extract_content
from site_steward.reviewer import analyze_content
from site_steward.taxonomy import MINISTRY_PROFILE


FIXTURE = Path(__file__).parent / "fixtures" / "sample_homepage.html"


class ExtractorTests(unittest.TestCase):
    def test_extracts_key_homepage_content(self) -> None:
        content = extract_content("https://example.com", FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(content.title, "JNSKM | Songs and Books for Weary Believers")
        self.assertIn("Music and books for weary believers", content.headings)
        self.assertIn("Start Here", content.navigation_labels)
        self.assertIn("Start Here", content.button_labels)
        self.assertEqual(content.image_alts_missing, 0)

    def test_ministry_profile_does_not_raise_false_positive_for_integrated_homepage(self) -> None:
        content = extract_content("https://example.com", FIXTURE.read_text(encoding="utf-8"))
        _, issues, _ = analyze_content(content, MINISTRY_PROFILE)

        issue_ids = {issue.id for issue in issues}
        self.assertNotIn("music-book-gap", issue_ids)
        self.assertNotIn("missing-meta-description", issue_ids)


if __name__ == "__main__":
    unittest.main()
