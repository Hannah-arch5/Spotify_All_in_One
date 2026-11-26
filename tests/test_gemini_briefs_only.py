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
import assemble_gemini_report_from_briefs as assembler


class BriefsOnlyTests(unittest.TestCase):
    def test_episode_prompt_contains_each_prose_field_once_in_locked_order(self):
        prompt = generator._episode_prompt("fixture", {
            "index": 1,
            "podcast_title": "Fixture Podcast",
            "episode_title": "Fixture Episode",
            "published_at": "2026-11-16T06:00:00+00:00",
            "transcript": {"plain_text": "A complete source transcript."},
        })

        summary_label = "- 核心内容摘要："
        value_label = "- 情报价值点："
        self.assertEqual(prompt.count(summary_label), 1)
        self.assertEqual(prompt.count(value_label), 1)
        self.assertLess(prompt.index(summary_label), prompt.index(value_label))
        self.assertIn("中文原句译成英文", prompt)

    def test_rejected_synthesis_revision_does_not_replace_cached_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            chunk_dir = Path(directory)
            cached = chunk_dir / "synthesis-fourth-latest.md"
            cached.write_text("## 第四部分：第二层思维\n\n旧稿", encoding="utf-8")
            parts = (
                "# 有效标题 (Valid English Translation)",
                "## 第一部分\n" + "甲" * 700,
                "## 第三部分\n" + "乙" * 1500,
                "## 第四部分\n" + "丙" * 2000,
                "## 第五部分\n**主题一：甲**\n**主题二：乙**\n**主题三：丙**\n" + "丁" * 1100 + "。",
            )
            with patch.object(assembler, "_generate_text", return_value="短文本"):
                with self.assertRaisesRegex(SystemExit, "revision failed quality gates"):
                    assembler._repair_synthesis_parts(
                        parts, ["第四部分当前过长"], run_id="fixture", report_date="261123",
                        report_window={}, compact_briefs=[], chunk_dir=chunk_dir,
                        model="fixture", timeout=1,
                    )
            self.assertEqual(cached.read_text(encoding="utf-8"), "## 第四部分：第二层思维\n\n旧稿")
            self.assertTrue((chunk_dir / "synthesis-fourth-rejected.md").exists())

    def test_targeted_prose_retry_replaces_only_requested_field(self):
        original = """- 核心内容摘要：原摘要
- 情报价值点：原价值
- 关键金句 / 结论：必须保留的原句
- 证据锚点：
  - [1:00] Verifiable source sentence."""
        response = """- 情报价值点：修正后第一段。

修正后第二段。"""
        replacement = generator._standalone_field(response, "情报价值点")
        updated = generator._replace_section(
            original, "情报价值点", "关键金句 / 结论", replacement
        )

        self.assertIn("修正后第一段", updated)
        self.assertNotIn("原价值", updated)
        self.assertIn("必须保留的原句", updated)
        self.assertIn("[1:00] Verifiable source sentence.", updated)

    def test_preserves_briefs_without_final_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            (package / "transcript-evidence-full.json").write_text(json.dumps({
                "run_id": "fixture", "episodes": [{"index": 1, "episode_title": "Fixture"}],
            }))
            summary_paragraph = "这是一段基于原始逐字稿的完整摘要，说明具体背景、行动、因果机制、限制条件与最终结论。" * 7
            value_paragraph = "这段情报价值说明企业决策意义、适用边界、验证指标和停止条件，避免空泛建议。" * 5
            brief = f"""#### Brief
- 核心内容摘要：{summary_paragraph}

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
