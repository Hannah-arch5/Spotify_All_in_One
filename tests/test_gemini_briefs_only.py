import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_chunked_gemini_report as generator


class BriefsOnlyTests(unittest.TestCase):
    def test_preserves_briefs_without_final_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            (package / "transcript-evidence-full.json").write_text(json.dumps({
                "run_id": "fixture", "episodes": [{"index": 1, "episode_title": "Fixture"}],
            }))
            with patch.object(generator, "ROOT", root), \
                    patch.object(generator, "_episode_prompt", return_value="fixture prompt"), \
                    patch.object(generator, "_generate_text", return_value="#### Brief") as generate, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = generator.generate_chunked(package, model="fixture", sleep_seconds=0,
                                                    resume=True, timeout=1, briefs_only=True)
                self.assertEqual(generate.call_count, 1)
                generator.generate_chunked(package, model="fixture", sleep_seconds=0,
                                           resume=True, timeout=1, briefs_only=True)
                self.assertEqual(generate.call_count, 1)
            self.assertEqual((result / "01-episode-brief.md").read_text(), "#### Brief\n")
            self.assertEqual(json.loads((result / "STATUS.json").read_text())["status"],
                             "briefs_complete_pending_synthesis")
            self.assertFalse((root / "reports").exists())


if __name__ == "__main__":
    unittest.main()
