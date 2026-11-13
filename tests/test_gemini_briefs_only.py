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
            summary_paragraph = "这是一段基于原始逐字稿的完整摘要，说明具体背景、行动、因果机制、限制条件与最终结论。" * 8
            value_paragraph = "这段情报价值说明企业决策意义、适用边界、验证指标和停止条件，避免空泛建议。" * 5
            brief = f"""#### Brief
- 核心内容摘要：{summary_paragraph}

{summary_paragraph}

{summary_paragraph}

{summary_paragraph}
- 情报价值点：{value_paragraph}

{value_paragraph}
- 关键金句 / 结论：
  1. A meaningful source quotation for verification.
- 证据锚点：
  - [1:00] This is a substantial source sentence with verifiable information.
    *这是一条包含可核验信息的实质性原文。*
  - [2:00] Another source sentence explains the relevant causal mechanism clearly.
    *另一条原文清楚解释了相关因果机制。*
  - [3:00] A final source sentence states an important boundary condition explicitly.
    *最后一条原文明示了重要的边界条件。*"""
            with patch.object(generator, "ROOT", root), \
                    patch.object(generator, "_episode_prompt", return_value="fixture prompt"), \
                    patch.object(generator, "_generate_text", return_value=brief) as generate, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = generator.generate_chunked(package, model="fixture", sleep_seconds=0,
                                                    resume=True, timeout=1, briefs_only=True)
                self.assertEqual(generate.call_count, 1)
                generator.generate_chunked(package, model="fixture", sleep_seconds=0,
                                           resume=True, timeout=1, briefs_only=True)
                self.assertEqual(generate.call_count, 1)
            self.assertEqual((result / "01-episode-brief.md").read_text(), brief + "\n")
            self.assertEqual(json.loads((result / "STATUS.json").read_text())["status"],
                             "briefs_complete_pending_synthesis")
            self.assertFalse((root / "reports").exists())


if __name__ == "__main__":
    unittest.main()
