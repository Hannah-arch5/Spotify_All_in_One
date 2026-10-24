from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from normalize_report_delivery_format import normalize


class EvidencePairTests(unittest.TestCase):
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
