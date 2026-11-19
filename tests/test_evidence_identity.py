import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_evidence_pack import _match_transcript


class EvidenceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"path": "a", "spotify_episode_id": "verified", "episode_title": "Changed title", "podcast_name": "Show"},
            {"path": "b", "spotify_episode_id": "other", "episode_title": "RSS title", "podcast_name": "Show"},
        ]
        self.episode = {"spotify_episode_id": "verified", "episode_title": "RSS title", "podcast_title": "Show"}

    def test_verified_id_overrides_a_better_title_match(self):
        used = set()
        result = _match_transcript(self.episode, self.rows, used)
        self.assertEqual(result["path"], "a")
        self.assertEqual(result["match_method"], "verified_spotify_id")
        self.assertEqual(used, {"a"})

    def test_missing_id_does_not_fall_back_to_same_title(self):
        episode = dict(self.episode, spotify_episode_id="missing")
        self.assertIsNone(_match_transcript(episode, self.rows, set()))

    def test_duplicate_identity_fails_closed(self):
        duplicate = dict(self.rows[0], path="duplicate")
        self.assertIsNone(_match_transcript(self.episode, self.rows + [duplicate], set()))

    def test_used_path_is_not_reused(self):
        self.assertIsNone(_match_transcript(self.episode, self.rows, {"a"}))

    def test_used_duplicate_does_not_hide_ambiguous_identity(self):
        duplicate = dict(self.rows[0], path="duplicate")
        self.assertIsNone(_match_transcript(self.episode, self.rows + [duplicate], {"duplicate"}))

    def test_official_source_identity_is_matched_without_a_spotify_id(self):
        episode = {"source_episode_id": "rss-guid"}
        rows = [{"source_episode_id": "rss-guid", "path": "official"}]
        result = _match_transcript(episode, rows, set())
        self.assertEqual(result["path"], "official")
        self.assertEqual(result["match_method"], "verified_source_id")

    def test_unverified_episode_keeps_existing_title_matching(self):
        episode = {"episode_title": "RSS title", "podcast_title": "Show"}
        self.assertEqual(_match_transcript(episode, self.rows, set())["path"], "b")

    def test_unverified_numbered_series_rejects_a_different_episode_number(self):
        episode = {
            "episode_title": "#2581 - Protect Our Parks 18",
            "podcast_title": "The Joe Rogan Experience",
            "published_at": "2026-11-13T18:30:00+00:00",
        }
        rows = [{
            "path": "old",
            "episode_title": "#2539 - Protect Our Parks 17",
            "podcast_name": "The Joe Rogan Experience",
            "published_date": "2026-08-13",
        }]
        self.assertIsNone(_match_transcript(episode, rows, set()))

    def test_unverified_title_match_rejects_a_distant_publication_date(self):
        episode = {
            "episode_title": "Same recurring title",
            "podcast_title": "Show",
            "published_at": "2026-11-13T18:30:00+00:00",
        }
        rows = [{
            "path": "old",
            "episode_title": "Same recurring title",
            "podcast_name": "Show",
            "published_date": "2026-08-13",
        }]
        self.assertIsNone(_match_transcript(episode, rows, set()))


if __name__ == "__main__":
    unittest.main()
