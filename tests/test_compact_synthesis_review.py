import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_gemini_report_from_briefs import _compact_brief
from check_gemini_report import _evidence_translation_findings, check


class CompactSynthesisReviewTests(unittest.TestCase):
    def test_compact_brief_preserves_core_mechanism(self):
        result = _compact_brief('#### 情报 1：工作流\n- 原始标题：Workflow\n- 核心内容摘要：先确认权限，再执行任务。\n- 情报价值点：衡量返工成本。\n- 关键金句 / 结论：真实原句\n- 证据锚点：\n  - [1:00] source')
        self.assertIn('先确认权限，再执行任务。', result)
        self.assertIn('衡量返工成本。', result)
        self.assertNotIn('[1:00]', result)

    def test_chinese_source_with_english_terms_needs_no_duplicate_translation(self):
        section = {'number': 1, 'body': '- 证据锚点：\n  - [10:10] 但是它的 computer use 功能可以直接根据简单的 prompt 完成操作，这仍然需要确认执行结果。'}
        self.assertEqual([], _evidence_translation_findings(section))

    def test_english_source_still_requires_italic_translation(self):
        section = {'number': 1, 'body': '- 证据锚点：\n  - [1:00] You cannot automate a process that does not exist.'}
        self.assertEqual(1, len(_evidence_translation_findings(section)))
        section['body'] += '\n    *你不能自动化一个不存在的流程。*'
        self.assertEqual([], _evidence_translation_findings(section))

    def test_untimed_official_source_rejects_fabricated_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            source.write_text(json.dumps({'segments': [{'timestamp': None, 'text': 'A meaningful source sentence.'}]}))
            evidence = root / 'evidence.json'
            evidence.write_text(json.dumps({'episodes': [{'index': 1, 'transcript': {'path': str(source)}}]}))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'episodes': [{'episode_title': 'Episode', 'episode_url': 'https://example.com/episode'}]}))
            report = root / 'report.md'
            report.write_text('''## 第一部分：摘要
## 第二部分：详情
#### 情报 1：主题
- 原始标题：Episode
- 原始链接：https://example.com/episode
- Transcript 来源：官方 TXT
- 关键金句 / 结论：
- 证据锚点：
  - [3:03] A meaningful source sentence.
    *有意义的原文句子。*
## 第三部分：分析
## 第四部分：思考
## 第五部分：结论
''')
            result = check(report, manifest, evidence)
            self.assertTrue(any('不得编造时间码' in finding['message'] for finding in result['findings']))
            report.write_text(report.read_text().replace('[3:03]', '[原文段落 1]'))
            result = check(report, manifest, evidence)
            self.assertFalse(any('不得编造时间码' in finding['message'] for finding in result['findings']))

    def test_rejects_stray_part_completion_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'episodes': []}))
            report = root / 'report.md'
            report.write_text('''## 第一部分：摘要
## 第二部分：详情
## 第三部分：分析
## 第四部分：思考
## 第四部分完
## 第五部分：结论
''')
            result = check(report, manifest)
            self.assertTrue(any('重复收尾标题' in finding['message'] for finding in result['findings']))

    def test_rejects_internal_generation_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'episodes': []}))
            report = root / 'report.md'
            report.write_text('''## 第一部分：摘要
## 第二部分：详情
## 第三部分：分析
## 第四部分：思考
Run ID: internal-run
Report Date: 2026-11-11
(Word Count: 2500 Chinese Characters)
## 第五部分：结论
''')
            result = check(report, manifest)
            self.assertTrue(any('内部运行或字数自检元数据' in finding['message'] for finding in result['findings']))

    def test_rejects_extra_h2_inside_integrated_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'episodes': []}))
            report = root / 'report.md'
            report.write_text('''## 第一部分：摘要
## 第二部分：详情
## 第三部分：分析
## 主题一：不应与五大部分同级
## 第四部分：思考
## 第五部分：结论
''')
            result = check(report, manifest)
            self.assertTrue(any('只能有五个二级主部分' in finding['message'] for finding in result['findings']))


if __name__ == '__main__':
    unittest.main()
