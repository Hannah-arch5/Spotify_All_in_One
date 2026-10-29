import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_transcript_languages import _score
from build_gemini_input_package import _load_transcript
from translate_spotify_transcripts_to_zh import _target_path
from import_official_vtt_transcript import read_vtt


class OfficialTranscriptIdentityTests(unittest.TestCase):
    def test_remote_vtt_request_uses_browser_headers(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b"WEBVTT\n"

        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        with patch("import_official_vtt_transcript.urllib.request.urlopen", side_effect=fake_urlopen):
            content, source = read_vtt({"transcript_url": "https://example.com/source.vtt"}, None)

        self.assertEqual(content, "WEBVTT\n")
        self.assertEqual(source, "https://example.com/source.vtt")
        self.assertEqual(captured["timeout"], 120)
        self.assertIn("Mozilla/5.0", captured["request"].get_header("User-agent"))

    def test_vtt_import_and_package_preserve_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"episodes": [{
                "guid": "rss-guid", "podcast_title": "Show", "episode_title": "Title",
                "published_at": "2026-10-18T00:00:00+00:00",
                "episode_url": "https://example.com/episode/rss-guid",
            }]}))
            vtt = root / "source.vtt"
            vtt.write_text("WEBVTT\n\n00:00.000 --> 00:02.000\nA meaningful sentence.\n")
            subprocess.run([
                sys.executable, str(ROOT / "scripts/import_official_vtt_transcript.py"),
                "--manifest", str(manifest), "--index", "1", "--vtt-file", str(vtt),
                "--language", "zh-CN", "--out-dir", str(root / "out"),
            ], check=True, capture_output=True, text=True)
            path = next((root / "out").glob("*.json"))
            source = json.loads(path.read_text())
            self.assertEqual(source["sourceEpisodeId"], "rss-guid")
            self.assertNotIn("spotifyEpisodeId", source)
            self.assertEqual(source["transcriptLanguage"], "zh-CN")
            self.assertTrue(_target_path(source, root).name.endswith("rss-guid.json"))
            package = _load_transcript({"path": str(path)})
            self.assertEqual(package["source_episode_id"], "rss-guid")
            self.assertIsNone(package["spotify_episode_id"])

    def test_language_audit_uses_source_identity_even_when_title_changes(self):
        episode = {"episode_title": "Old title", "transcript": {"source_episode_id": "rss-guid"}}
        self.assertEqual(_score(episode, {"source_episode_id": "rss-guid", "episode_title": "New title"}), 1.0)

    def test_language_audit_rejects_conflicting_source_ids_despite_equal_titles(self):
        episode = {"episode_title": "Title", "podcast_title": "Show", "transcript": {"source_episode_id": "rss-guid"}}
        self.assertEqual(_score(episode, {"source_episode_id": "other", "episode_title": "Title", "podcast_name": "Show"}), 0.0)


if __name__ == "__main__":
    unittest.main()
