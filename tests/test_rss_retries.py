from http.client import IncompleteRead
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_new_episodes import _fetch_and_parse_with_retry
from src.config import Podcast
from src.rss import fetch_feed


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.content


class RssRetryTests(unittest.TestCase):
    def test_fetch_feed_retries_incomplete_read_instead_of_returning_partial_xml(self):
        partial = IncompleteRead(b"<rss><channel>", 100)
        complete = b"<rss><channel></channel></rss>"
        with patch("src.rss.urlopen", side_effect=[partial, _Response(complete)]) as mocked, patch(
            "src.rss.time.sleep"
        ):
            self.assertEqual(fetch_feed("https://example.com/feed", attempts=2), complete)
        self.assertEqual(mocked.call_count, 2)

    def test_fetch_feed_fails_closed_when_every_response_is_incomplete(self):
        partial = IncompleteRead(b"<rss><channel>", 100)
        with patch("src.rss.urlopen", side_effect=[partial, partial]), patch("src.rss.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "after 2 attempts"):
                fetch_feed("https://example.com/feed", attempts=2)

    def test_manifest_fetch_retries_malformed_xml_before_accepting_feed(self):
        podcast = Podcast(1, "Show", "Publisher", "en", "include", "https://example.com/feed", None, "")
        complete = b"<rss><channel><item><guid>episode-1</guid><title>Episode</title></item></channel></rss>"
        with patch(
            "scripts.check_new_episodes.fetch_feed",
            side_effect=[b"<rss><channel>", complete],
        ) as mocked, patch("scripts.check_new_episodes.time.sleep"):
            xml_bytes, episodes = _fetch_and_parse_with_retry(podcast, attempts=2)
        self.assertEqual(xml_bytes, complete)
        self.assertEqual([episode.guid for episode in episodes], ["episode-1"])
        self.assertEqual(mocked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
