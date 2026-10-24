import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backup_spotify_transcripts_to_drive import file_record, inventory, transfer, verify_remote


class TranscriptDriveBackupTests(unittest.TestCase):
    def make_file(self, folder, name, episode_id, text="This is a complete sentence.", translation=None):
        folder.mkdir(exist_ok=True)
        data = {"spotifyEpisodeId": episode_id, "podcastName": "Show", "episodeTitle": episode_id,
                "segments": [{"text": text}]}
        if translation:
            data["segments"][0]["translation"] = translation
        path = folder / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_routes_actual_chinese_originals_out_of_english_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            en, zh = root / "en", root / "zh"
            english = self.make_file(en, "english.json", "en")
            self.make_file(en, "chinese.json", "cn", "这是完整的中文播客原文内容。")
            self.make_file(zh, "english_zh.json", "en", translation="这是一句完整的话。")
            chinese = self.make_file(zh, "chinese_zh.json", "cn", "这是完整的中文播客原文内容。", "这是完整的中文播客原文内容。")
            plan = inventory(en, zh)
            self.assertEqual(plan["english"], [english])
            self.assertIn(chinese, plan["chinese"])
            self.assertEqual(plan["chinese_original_count"], 1)
            self.assertFalse(plan["missing_chinese_sources"])

    def test_incomplete_chinese_is_not_backed_up_as_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            en = self.make_file(root / "en", "en.json", "id")
            zh = self.make_file(root / "zh", "bad.json", "id")
            plan = inventory(root / "en", root / "zh")
            self.assertEqual(plan["chinese"], [])
            self.assertEqual(plan["incomplete_chinese_files"], [str(zh)])
            self.assertEqual(plan["missing_chinese_sources"], [str(en)])

    def test_duplicate_identity_fails_before_transfer(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_file(root / "en", "a.json", "same")
            self.make_file(root / "en", "b.json", "same")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                inventory(root / "en", root / "zh")

    def test_conflicting_ids_never_match_by_title(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            en = self.make_file(root / "en", "en.json", "original")
            zh = self.make_file(root / "zh", "zh.json", "different", translation="翻译内容。")
            data = json.loads(zh.read_text())
            data["episodeTitle"] = "original"
            zh.write_text(json.dumps(data))
            self.assertEqual(inventory(root / "en", root / "zh")["missing_chinese_sources"], [str(en)])

    def test_remote_verification_requires_unique_file_and_matching_size_md5(self):
        local = [{"name": "a.json", "size": 10, "md5": "abc"}]
        remote = [{"Name": "a.json", "Size": 10, "Hashes": {"MD5": "abc"}}]
        verify_remote(local, remote)
        for rows in ([], remote + remote, [{**remote[0], "Size": 11}],
                     [{**remote[0], "Hashes": {"MD5": "bad"}}]):
            with self.assertRaises(ValueError):
                verify_remote(local, rows)

    def test_evidence_pack_limits_backup_to_its_own_window(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = self.make_file(root / "en", "current.json", "current")
            self.make_file(root / "en", "other.json", "other")
            translated = self.make_file(root / "zh", "current_zh.json", "current", translation="翻译内容。")
            self.make_file(root / "zh", "other_zh.json", "other", translation="其他翻译。")
            evidence = root / "pack.json"
            evidence.write_text(json.dumps({"episodes": [{"transcript": {"path": str(current)}}]}))
            plan = inventory(root / "en", root / "zh", evidence)
            self.assertEqual(plan["english"], [current])
            self.assertEqual(plan["chinese"], [translated])

    def test_transfer_pins_folder_and_never_deletes_remote_extras(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = self.make_file(root / "en", "a.json", "id")
            record = file_record(source)
            remote = [{"Name": source.name, "Size": record["size"], "Hashes": {"MD5": record["md5"]}},
                      {"Name": "unrelated.json", "Size": 0, "Hashes": {"MD5": "other"}}]
            with patch("backup_spotify_transcripts_to_drive.subprocess.run") as run:
                run.return_value = SimpleNamespace(stdout=json.dumps(remote))
                result = transfer([source], root / "en", "pinned-folder", "gdrive:", root, "english")
            self.assertEqual(result["status"], "verified")
            copy_command = run.call_args_list[0].args[0]
            self.assertEqual(copy_command[1], "copy")
            self.assertIn("--checksum", copy_command)
            self.assertEqual(copy_command[copy_command.index("--drive-root-folder-id") + 1], "pinned-folder")
            self.assertFalse(any("delete" in part or part == "sync" for part in copy_command))


if __name__ == "__main__":
    unittest.main()
