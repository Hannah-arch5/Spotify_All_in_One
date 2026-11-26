import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_aidailybrief_official_md import parse_markdown
from import_official_pdf_transcript import parse_speaker_turns


class OfficialMdPdfImportTests(unittest.TestCase):
    def test_markdown_preserves_only_real_timestamps(self):
        segments = parse_markdown(
            "# Episode — Transcript (2026-11-24)\n\nSource link\n\n---\n"
            "[00:00:00] First sentence.\n\n[00:01:00] Second sentence.\n"
        )
        self.assertEqual([item["timestamp"] for item in segments], ["00:00:00", "00:01:00"])
        self.assertEqual([item["text"] for item in segments], ["First sentence.", "Second sentence."])

    def test_pdf_preserves_speaker_turns_without_timestamps_or_page_numbers(self):
        segments = parse_speaker_turns([
            "Report title\nAllison Nathan: A question that continues\n1",
            "on the next page.\nChamath Palihapitiya: An answer.\n2\nEric Sheridan: Another answer.",
        ])
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0]["text"], "A question that continues on the next page.")
        self.assertEqual(segments[1]["speaker"], "Chamath Palihapitiya")
        self.assertTrue(all(item["timestamp"] is None for item in segments))


if __name__ == "__main__":
    unittest.main()
