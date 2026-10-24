import copy
import contextlib
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_transcript_retention import backup_records, build_plan, calendar_cutoff, chinese_preserves_original
import apply_transcript_retention as retention


class TranscriptRetentionTests(unittest.TestCase):
    def write(self, root, language, name, data):
        folder = root / language
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def pair(self, root, published="2025-01-01", text="A full English transcript."):
        original = {"spotifyEpisodeId": "id", "podcastName": "Show", "episodeTitle": "Title",
                    "publishedDate": published, "segments": [{"text": text}], "debugLogs": ["capture"]}
        en = self.write(root, "spotify_en", "en.json", original)
        translated = copy.deepcopy(original)
        translated["segments"][0]["translation"] = "完整的翻译。"
        translated["sourceTranscriptSha256"] = hashlib.sha256(en.read_bytes()).hexdigest()
        translated["debugLogs"].append("translated")
        zh = self.write(root, "spotify_zh", "zh.json", translated)
        records = {"english": {en.name: {"sha256": hashlib.sha256(en.read_bytes()).hexdigest()}},
                   "chinese": {zh.name: {"sha256": hashlib.sha256(zh.read_bytes()).hexdigest()}}}
        return en, zh, original, translated, records

    def test_cutoff_uses_calendar_months_and_handles_leap_year(self):
        self.assertEqual(calendar_cutoff(date(2026, 8, 31)), date(2026, 2, 28))
        self.assertEqual(calendar_cutoff(date(2024, 8, 31)), date(2024, 2, 29))
        self.assertEqual(calendar_cutoff(date(2027, 1, 1)), date(2026, 7, 1))

    def test_old_verified_pair_is_eligible_but_planning_never_deletes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            en, zh, _, _, records = self.pair(root)
            rows = build_plan(root, date(2026, 4, 24), records, (set(), set(), set()))
            self.assertTrue(all(r["action"] == "delete" for r in rows))
            self.assertTrue(en.exists() and zh.exists())

    def test_missing_cloud_proof_preserves_both_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.pair(root)
            rows = build_plan(root, date(2026, 4, 24), {}, (set(), set(), set()))
            self.assertTrue(all(r["action"] == "keep" for r in rows))

    def test_boundary_date_and_pending_reports_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, _, _, records = self.pair(root, "2026-04-24")
            rows = build_plan(root, date(2026, 4, 24), records, (set(), set(), set()))
            self.assertTrue(all(r["reason"] == "within_retention_window" for r in rows))
            self.pair(root, "2025-01-01")
            rows = build_plan(root, date(2026, 4, 24), records, ({"id"}, set(), set()))
            self.assertTrue(all(r["reason"] == "pending_report" for r in rows))

    def test_missing_chinese_keeps_original_for_backfill(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, zh, _, _, records = self.pair(root)
            zh.unlink()
            rows = build_plan(root, date(2026, 4, 24), records, (set(), set(), set()))
            self.assertEqual(rows[0]["reason"], "pending_chinese_backfill")

    def test_chinese_original_requires_verified_lossless_chinese_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, original, translated, records = self.pair(root, text="这是完整的中文播客原文内容。")
            source_hash = translated["sourceTranscriptSha256"]
            self.assertTrue(chinese_preserves_original(original, translated, source_hash))
            changed = copy.deepcopy(translated)
            changed["segments"][0]["text"] = "Different source"
            self.assertFalse(chinese_preserves_original(original, changed, source_hash))
            records["english"] = {}
            rows = build_plan(root, date(2026, 4, 24), records, (set(), set(), set()))
            self.assertTrue(all(r["action"] == "delete" for r in rows))

    def test_receipt_must_be_fresh_verified_and_target_the_pinned_folder(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            now = datetime.now(timezone.utc)
            payload = {"status": "verified_available_archive_backup", "completed_at": now.isoformat(),
                       "english": {"status": "verified", "folder_id": "correct", "files": [{"name": "a", "sha256": "hash"}]}}
            with patch.dict(os.environ, {"SPOTIFY_TRANSCRIPT_DRIVE_FOLDER_ID": "correct"}):
                path.write_text(json.dumps(payload))
                self.assertIn("a", backup_records([path], now)["english"])
                for change in ({"status": "failed"}, {"completed_at": (now - timedelta(hours=2)).isoformat()},
                               {"english": {**payload["english"], "folder_id": "wrong"}}):
                    path.write_text(json.dumps({**payload, **change}))
                    with self.assertRaises(ValueError):
                        backup_records([path], now)

    def test_delete_cli_requires_proof_and_only_removes_verified_fixture_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            transcripts = root / "data/transcripts"
            transcripts.mkdir(parents=True)
            en, zh, _, _, records = self.pair(transcripts)
            (root / "data/runs").mkdir()
            with sqlite3.connect(root / "data/state.sqlite") as connection:
                connection.execute("create table processed_episodes (guid text)")
            unrelated = root / "unrelated.json"
            unrelated.write_text("keep")
            receipt = root / "receipt.json"
            payload = {"status": "verified_available_archive_backup", "completed_at": datetime.now(timezone.utc).isoformat()}
            for language in ("english", "chinese"):
                payload[language] = {"status": "verified", "folder_id": language,
                                     "files": [{"name": name, **record} for name, record in records[language].items()]}
            receipt.write_text(json.dumps(payload))
            argv = ["prune", "--delete", "--plan-json", str(root / "plan.json")]
            env = {"SPOTIFY_TRANSCRIPT_DRIVE_FOLDER_ID": "english", "SPOTIFY_TRANSCRIPT_ZH_DRIVE_FOLDER_ID": "chinese"}
            with patch.object(retention, "ROOT", root), patch.object(retention, "load_project_env"), \
                    patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
                with patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                    retention.main()
                self.assertTrue(en.exists() and zh.exists())
                with patch.object(sys, "argv", argv + ["--backup-receipt", str(receipt)]):
                    retention.main()
            self.assertFalse(en.exists() or zh.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
