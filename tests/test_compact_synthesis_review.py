import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_gemini_report_from_briefs import _compact_brief, _normalize_brief, _synthesis_issues
from check_gemini_report import _evidence_translation_findings, check


class CompactSynthesisReviewTests(unittest.TestCase):
    def test_normalize_brief_restores_title_and_source_quote_style(self):
        brief = '''#### 情报 1：主题

- 核心内容摘要：术语（

earnestness）不应断开。
- 关键金句 / 结论：
  - *Original source sentence.*
    *原句翻译。*
- 证据锚点：
  - [1:00] Speaker 1: Original source sentence.
    *原句翻译。*'''
        normalized = _normalize_brief(brief, {'episode_title': 'Original | Title'})
        self.assertIn('- 原始标题：Original | Title', normalized)
        self.assertIn('（earnestness）', normalized)
        self.assertIn('  - Original source sentence.', normalized)
        self.assertIn('  - [1:00] Original source sentence.', normalized)

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

    def test_enforces_episode_prose_targets_with_authorized_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'episodes': [{'episode_title': 'Episode', 'episode_url': 'https://example.com/episode'}]
            }))
            report = root / 'report.md'

            def report_text(summary_length, value_length):
                return f'''## 第一部分：摘要
## 第二部分：详情
#### 情报 1：主题
- 原始标题：Episode
- 原始链接：https://example.com/episode
- Transcript 来源：官方 TXT
- 核心内容摘要：{'摘' * summary_length}
- 情报价值点：{'值' * value_length}
- 关键金句 / 结论：
- 证据锚点：
## 第三部分：分析
## 第四部分：思考
## 第五部分：结论
'''

            report.write_text(report_text(900, 400))
            result = check(report, manifest)
            self.assertFalse(any('允许容差' in finding['message'] for finding in result['findings']))

            report.write_text(report_text(849, 501))
            result = check(report, manifest)
            self.assertFalse(any('允许容差' in finding['message'] for finding in result['findings']))

            report.write_text(report_text(799, 551))
            result = check(report, manifest)
            messages = [finding['message'] for finding in result['findings']]
            self.assertTrue(any('核心内容摘要为 799 字' in message for message in messages))
            self.assertTrue(any('情报价值点为 551 字' in message for message in messages))

    def test_rejects_unqualified_nvidia_allegation(self):
        parts = (
            '# AI 研发自动化正在改变科技企业增长逻辑 (AI R&D Automation Is Changing Growth)',
            '## 第一部分：摘要 (Summary)\n\n' + '黄仁勋因间谍丑闻下台。' + '甲' * 700,
            '## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)\n\n' + '甲' * 1500,
            '## 第四部分：第二层思维 (Second-Order Thinking)\n\n' + '甲' * 1000,
            '## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)\n\n' + '甲' * 1100,
        )
        issues = _synthesis_issues(parts)
        self.assertTrue(any('未经独立核验' in issue for issue in issues))

    def test_first_section_omits_even_attributed_nvidia_allegation(self):
        parts = (
            '# AI 研发自动化正在改变科技企业增长逻辑 (AI R&D Automation Is Changing Growth)',
            '## 第一部分：摘要 (Summary)\n\n'
            + '节目声称黄仁勋因间谍丑闻下台，但该叙述未经本项目独立核验。'
            + '甲' * 700,
            '## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)\n\n' + '甲' * 1500,
            '## 第四部分：第二层思维 (Second-Order Thinking)\n\n' + '甲' * 1000,
            '## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)\n\n' + '甲' * 1100,
        )
        issues = _synthesis_issues(parts)
        self.assertTrue(any('未经独立核验' in issue for issue in issues))

    def test_fifth_section_rejects_missing_themes_and_invented_schedule(self):
        parts = (
            '# AI 协作能力决定经济价值兑现速度 (AI Coordination Determines Value Realization)',
            '## 第一部分：摘要 (Summary)\n\n' + '甲' * 700,
            '## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)\n\n' + '甲' * 1500,
            '## 第四部分：第二层思维 (Second-Order Thinking)\n\n' + '甲' * 1000,
            '## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)\n\n'
            + '**主题一：测试**\n\n未来6-12个月投入预算的30%。'
            + '甲' * 1050,
        )
        issues = _synthesis_issues(parts)
        self.assertTrue(any('独立主题仅' in issue for issue in issues))
        self.assertTrue(any('统一未来时间表' in issue for issue in issues))
        self.assertTrue(any('固定预算或绩效百分比' in issue for issue in issues))

    def test_fifth_section_accepts_three_complete_bounded_themes(self):
        fifth = '## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)\n\n'
        fifth += '\n\n'.join(
            f'**主题{name}：测试**\n\n' + ('判断与行动。' * 75)
            for name in ['一', '二', '三']
        )
        parts = (
            '# AI 协作能力决定经济价值兑现速度 (AI Coordination Determines Value Realization)',
            '## 第一部分：摘要 (Summary)\n\n' + '甲' * 700,
            '## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)\n\n' + '甲' * 1500,
            '## 第四部分：第二层思维 (Second-Order Thinking)\n\n' + '甲' * 1000,
            fifth,
        )
        self.assertFalse(any(issue.startswith('第五部分') for issue in _synthesis_issues(parts)))


if __name__ == '__main__':
    unittest.main()
