from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_gemini_report import _key_quote_quality_findings


class KeyQuoteQualityTests(unittest.TestCase):
    def test_rejects_more_than_three_quote_pairs(self):
        body = "- 关键金句 / 结论：\n" + "\n".join(
            f"  - Complete source quotation number {index}.\n    *完整翻译第{index}条。*"
            for index in range(1, 5)
        ) + "\n- 证据锚点：\n"
        findings = _key_quote_quality_findings({"number": 6, "body": body})
        self.assertTrue(any("1-3 条" in finding.message for finding in findings))

    def test_rejects_short_dialogue_fragment(self):
        body = """- 关键金句 / 结论：
  - Well, yeah.
    *嗯，是的。*
- 证据锚点：
"""
        findings = _key_quote_quality_findings({"number": 6, "body": body})
        self.assertTrue(any("短回应或残句" in finding.message for finding in findings))

    def test_accepts_two_substantive_quote_pairs(self):
        body = """- 关键金句 / 结论：
  - This complete source quotation states a meaningful mechanism clearly.
    *这条完整原句清楚说明了一个有意义的机制。*
  - Another complete quotation explains the relevant strategic consequence.
    *另一条完整原句解释了相关战略后果。*
- 证据锚点：
"""
        self.assertEqual(
            _key_quote_quality_findings({"number": 6, "body": body}),
            [],
        )


if __name__ == "__main__":
    unittest.main()
