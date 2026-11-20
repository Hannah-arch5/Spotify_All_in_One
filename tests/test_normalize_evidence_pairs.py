from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from normalize_report_delivery_format import normalize, normalize_cjk_spacing


class EvidencePairTests(unittest.TestCase):
    def test_removes_cjk_tokenization_spaces_without_joining_latin_terms(self):
        source = "我 认 为 PA 是 一 个 正 确 的 方 向， 也 需 要 安 全 可 行。"
        self.assertEqual(
            normalize_cjk_spacing(source),
            "我认为 PA 是一个正确的方向，也需要安全可行。",
        )

    def test_preserves_whole_source_with_its_translation(self):
        source = '  - [1:00] Speaker 2: This is a meaningful first sentence about reliability. This second sentence adds the constraint.'
        translation = '    *这是关于可靠性的第一句。第二句补充了约束条件。*'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text('#### 情报 1：测试\n- 证据锚点：\n' + source + '\n' + translation + '\n')
            normalize(path)
            self.assertIn('This second sentence adds the constraint.', path.read_text())
            self.assertIn(translation, path.read_text())
            self.assertNotIn('Speaker 2:', path.read_text())
            self.assertFalse(normalize(path))


if __name__ == "__main__":
    unittest.main()
