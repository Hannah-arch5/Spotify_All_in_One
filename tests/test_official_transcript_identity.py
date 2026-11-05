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
from import_official_txt_transcript import parse_txt
from import_castbox_transcript import parse_transcription
from ingest_verified_std_download import normalized, same_show_name


class OfficialTranscriptIdentityTests(unittest.TestCase):
    def test_show_name_allows_only_exact_token_reordering(self):
        rss = normalized("Lenny's Podcast: Product | Growth | Career")
        self.assertTrue(same_show_name(rss, normalized("Lenny's Podcast: Product | Career | Growth")))
        self.assertFalse(same_show_name(rss, normalized("Another Podcast: Product | Career | Growth")))

    def test_official_txt_preserves_speaker_without_inventing_timestamps(self):
        segments = parse_txt("John Collison\r\nA question.\r\n\r\nSam Altman\r\nAn answer.\r\n")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1]["speaker"], "Sam Altman")
        self.assertEqual(segments[1]["text"], "An answer.")
        self.assertIsNone(segments[1]["timestamp"])

    def test_generic_std_download_requires_exact_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"new_episodes": [{
                "podcast_title": "The AI Daily Brief", "episode_title": "The New Model",
                "published_at": "2026-10-30T00:00:00+00:00",
            }]}))
            download = root / "download.json"
            download.write_text(json.dumps({
                "spotifyEpisodeId": "correct-id", "podcastName": "The AI Daily Brief: Artificial Intelligence News and Analysis",
                "episodeTitle": "The New Model", "transcriptLanguage": "en-us",
                "segments": [{"text": "A source sentence."}],
            }))
            command = [
                sys.executable, str(ROOT / "scripts/ingest_verified_std_download.py"),
                "--manifest", str(manifest), "--index", "1", "--spotify-id", "correct-id",
                "--download", str(download), "--out-dir", str(root / "out"),
            ]
            rejected = subprocess.run(command[:-5] + ["wrong-id"] + command[-4:], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertTrue(download.exists())
            accepted = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn("download_removed=true", accepted.stdout)
            self.assertFalse(download.exists())
            self.assertEqual(len(list((root / "out").glob("*.json"))), 1)

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

    def test_castbox_import_preserves_non_spotify_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"episodes": [{
                "guid": "rss-guid",
                "podcast_title": "Show",
                "episode_title": "Title",
                "published_at": "2026-11-03T00:00:00+00:00",
                "episode_url": "https://example.com/episode/rss-guid",
            }]}))
            source = root / "castbox.json"
            source.write_text(json.dumps({
                "result": {"language": "en-US"},
                "transcription": [
                    {
                        "text": f"Meaningful sentence {index}.",
                        "offsets": {"from": index * 1000, "to": (index + 1) * 1000},
                    }
                    for index in range(20)
                ],
            }))
            subprocess.run([
                sys.executable,
                str(ROOT / "scripts/import_castbox_transcript.py"),
                "--manifest", str(manifest),
                "--index", "1",
                "--transcript-file", str(source),
                "--castbox-eid", "12345",
                "--transcript-url", "https://example.com/castbox/12345",
                "--out-dir", str(root / "out"),
            ], check=True, capture_output=True, text=True)
            path = next((root / "out").glob("*.json"))
            transcript = json.loads(path.read_text())
            self.assertEqual(transcript["sourceEpisodeId"], "castbox:12345")
            self.assertNotIn("spotifyEpisodeId", transcript)
            self.assertEqual(transcript["source"], "castbox_public_asr")
            self.assertEqual(len(parse_transcription(json.loads(source.read_text()))), 20)

    def test_language_audit_uses_source_identity_even_when_title_changes(self):
        episode = {"episode_title": "Old title", "transcript": {"source_episode_id": "rss-guid"}}
        self.assertEqual(_score(episode, {"source_episode_id": "rss-guid", "episode_title": "New title"}), 1.0)

    def test_language_audit_rejects_conflicting_source_ids_despite_equal_titles(self):
        episode = {"episode_title": "Title", "podcast_title": "Show", "transcript": {"source_episode_id": "rss-guid"}}
        self.assertEqual(_score(episode, {"source_episode_id": "other", "episode_title": "Title", "podcast_name": "Show"}), 0.0)


if __name__ == "__main__":
    unittest.main()
