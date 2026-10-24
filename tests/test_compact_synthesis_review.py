import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_gemini_report_from_briefs import _compact_brief
from check_gemini_report import _evidence_translation_findings


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


if __name__ == '__main__':
    unittest.main()
