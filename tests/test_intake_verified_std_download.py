import json
from pathlib import Path
import tempfile
import unittest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from intake_verified_std_download import existing_archive_is_invalid, validate_segments


def payload(count=20, text="A complete transcript sentence with useful content."):
    return {"segments": [{"timestamp": f"0:{index:02d}", "text": text} for index in range(count)]}


class IntakeVerifiedStdDownloadTests(unittest.TestCase):
    def test_rejects_player_progress_false_positive(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            validate_segments({"segments": [{"speaker": "Change progress", "text": "4:11"}]})

    def test_accepts_substantive_transcript(self):
        self.assertEqual(len(validate_segments(payload())), 20)

    def test_existing_archive_is_invalid_only_when_quality_gate_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text(json.dumps({"segments": [{"text": "4:11"}]}), encoding="utf-8")
            self.assertTrue(existing_archive_is_invalid(path))
            path.write_text(json.dumps(payload()), encoding="utf-8")
            self.assertFalse(existing_archive_is_invalid(path))


if __name__ == "__main__":
    unittest.main()
