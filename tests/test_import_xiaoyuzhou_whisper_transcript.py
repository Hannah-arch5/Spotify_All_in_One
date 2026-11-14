import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from import_xiaoyuzhou_whisper_transcript import normalize_segments, parse_duration, xiaoyuzhou_id


class XiaoyuzhouWhisperImportTests(unittest.TestCase):
    def test_identity_and_duration_parsing(self):
        self.assertEqual(
            xiaoyuzhou_id("https://www.xiaoyuzhoufm.com/episode/6af5debf14d01a26f8a900ac?utm_source=rss"),
            "6af5debf14d01a26f8a900ac",
        )
        self.assertEqual(parse_duration("06:27:27"), 23247.0)

    def test_rejects_partial_transcript(self):
        payload = {"segments": [{"start": index, "end": index + 1, "text": "完整内容" * 10} for index in range(20)]}
        with self.assertRaisesRegex(ValueError, "below 95%"):
            normalize_segments(payload, 1000)


if __name__ == "__main__":
    unittest.main()
