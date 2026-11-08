import json
import hashlib
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
from import_youtube_transcript_txt import parse_transcript as parse_youtube_transcript, youtube_id
from ingest_verified_std_download import normalized, same_show_name
from check_pdf_heading_positions import _plain


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
            archived_path = next((root / "out").glob("*.json"))
            archived = json.loads(archived_path.read_text())
            self.assertEqual(archived["episodeTitle"], "The New Model")
            self.assertEqual(archived["podcastName"], "The AI Daily Brief")
            self.assertEqual(archived["publishedDate"], "2026-10-30")
            self.assertEqual(archived["episodeUrl"], "https://open.spotify.com/episode/correct-id")

    def test_youtube_transcript_preserves_verified_non_spotify_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"episodes": [{
                "guid": "rss-guid",
                "podcast_title": "Show",
                "episode_title": "Title",
                "published_at": "2026-11-04T00:00:00+00:00",
                "episode_url": "https://example.com/rss-guid",
            }]}))
            transcript = root / "youtube.txt"
            transcript.write_text(
                "Video ID: abc123\n" + "\n".join(
                    f"[00:{index:02d}] Meaningful source sentence {index}." for index in range(20)
                )
            )
            subprocess.run([
                sys.executable,
                str(ROOT / "scripts/import_youtube_transcript_txt.py"),
                "--manifest", str(manifest),
                "--index", "1",
                "--transcript-file", str(transcript),
                "--source-url", "https://www.youtube.com/watch?v=abc123",
                "--out-dir", str(root / "out"),
            ], check=True, capture_output=True, text=True)
            archived = json.loads(next((root / "out").glob("*.json")).read_text())
            self.assertEqual(archived["sourceEpisodeId"], "youtube:abc123")
            self.assertNotIn("spotifyEpisodeId", archived)
            self.assertEqual(archived["transcriptUrl"], "https://www.youtube.com/watch?v=abc123")
            self.assertEqual(len(archived["segments"]), 20)

    def test_youtube_helpers_parse_time_and_common_urls(self):
        segments = parse_youtube_transcript("[00:01] First line.\ncontinued\n[01:02:03] Second line.\n")
        self.assertEqual(segments[0]["text"], "First line. continued")
        self.assertEqual(segments[0]["end"], 3723.0)
        self.assertEqual(youtube_id("https://youtu.be/abc123"), "abc123")
        self.assertEqual(youtube_id("https://www.youtube.com/watch?v=abc123"), "abc123")

    def test_heading_match_normalizes_word_compatibility_glyphs(self):
        self.assertEqual(_plain("跨节⽬专题分析"), _plain("跨节目专题分析"))

    def test_manifest_metadata_normalizer_updates_original_and_chinese_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.json"
            original.write_text(json.dumps({
                "spotifyEpisodeId": "episode-id",
                "episodeTitle": "Wrong title",
                "podcastName": "Wrong show",
                "publishedDate": "2026-01-01",
                "segments": [{"text": "Source sentence."}],
            }))
            chinese_dir = root / "zh"
            chinese_dir.mkdir()
            chinese = chinese_dir / "old-name.json"
            chinese.write_text(json.dumps({
                "spotifyEpisodeId": "episode-id",
                "segments": [{"text": "Source sentence.", "translation": "来源句子。"}],
            }))
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps({"episodes": [{
                "episode_title": "Canonical title",
                "podcast_title": "Canonical show",
                "published_at": "2026-11-04T18:00:00+00:00",
                "transcript": {"path": str(original)},
            }]}))
            subprocess.run([
                sys.executable,
                str(ROOT / "scripts/normalize_transcript_manifest_metadata.py"),
                str(evidence),
                "--chinese-dir", str(chinese_dir),
            ], check=True, capture_output=True, text=True)
            normalized_original = json.loads(original.read_text())
            self.assertEqual(normalized_original["episodeTitle"], "Canonical title")
            self.assertEqual(normalized_original["podcastName"], "Canonical show")
            self.assertEqual(normalized_original["publishedDate"], "2026-11-04")
            normalized_chinese_path = next(chinese_dir.glob("*.json"))
            normalized_chinese = json.loads(normalized_chinese_path.read_text())
            self.assertIn("2026-11-04", normalized_chinese_path.name)
            self.assertEqual(normalized_chinese["episodeTitle"], "Canonical title")
            self.assertEqual(
                normalized_chinese["sourceTranscriptSha256"],
                hashlib.sha256(original.read_bytes()).hexdigest(),
            )

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
