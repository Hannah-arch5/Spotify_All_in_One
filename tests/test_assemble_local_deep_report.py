import unittest

from scripts.assemble_local_deep_report import has_chinese_translation, select_evidence, timestamp


class LocalDeepReportTests(unittest.TestCase):
    def test_english_evidence_requires_actual_chinese_translation(self) -> None:
        segments = [
            {"text": f"This is a meaningful mechanism with a concrete cost and decision number {index}."}
            for index in range(20)
        ]
        translations = [
            {"translation": segment["text"]}
            for segment in segments
        ]
        translations[9] = {"translation": "这是一条包含具体机制、成本和决策的有效中文翻译。"}

        selected = select_evidence(segments, translations, source_is_zh=False, count=1)

        self.assertEqual([9], selected)
        self.assertFalse(has_chinese_translation(translations[0]))
        self.assertTrue(has_chinese_translation(translations[9]))

    def test_untimed_evidence_uses_stable_paragraph_number(self) -> None:
        self.assertEqual("原文段落 8", timestamp({"text": "untimed"}, 7))


if __name__ == "__main__":
    unittest.main()

