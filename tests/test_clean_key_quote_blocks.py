from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from clean_key_quote_blocks import clean_markdown


class CleanKeyQuoteBlocksTests(unittest.TestCase):
    def test_removes_prefix_timestamps_from_quote_bullets(self):
        source = """- 关键金句 / 结论：
  - [09:08] First quote.
  - (1:02:03) Second quote.
  - 04:26 Third quote.
- 证据锚点：
  - [09:08] Evidence timestamp must remain.
"""

        self.assertEqual(
            clean_markdown(source),
            """- 关键金句 / 结论：
  - First quote.
  - Second quote.
  - Third quote.
- 证据锚点：
  - [09:08] Evidence timestamp must remain.
""",
        )


if __name__ == "__main__":
    unittest.main()
