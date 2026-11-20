from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from email.utils import format_datetime
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from http.client import IncompleteRead
import re
import signal
import socket
import time
import xml.etree.ElementTree as ET


ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
PODCAST_NS = "{https://podcastindex.org/namespace/1.0}"


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_next_data = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == "__NEXT_DATA__":
            self.in_next_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_next_data:
            self.in_next_data = False

    def handle_data(self, data: str) -> None:
        if self.in_next_data:
            self.parts.append(data)


@dataclass(frozen=True)
class Episode:
    podcast_title: str
    podcast_publisher: str
    guid: str
    title: str
    published_at: datetime | None
    episode_url: str | None
    audio_url: str | None
    duration: str | None
    description: str
    transcript_url: str | None
    transcript_type: str | None


def fetch_feed(url: str, timeout: int = 300, attempts: int = 3) -> bytes:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    def _timeout_handler(signum: int, frame: object) -> None:
        raise TimeoutError(f"Timed out reading feed after {timeout}s")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(url, headers={"User-Agent": "Spotify-All-in-One/0.1"})
        previous_timeout = socket.getdefaulttimeout()
        previous_handler = signal.getsignal(signal.SIGALRM)
        try:
            socket.setdefaulttimeout(timeout)
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout)
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (IncompleteRead, TimeoutError, socket.timeout, URLError) as exc:
            last_error = exc
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
            socket.setdefaulttimeout(previous_timeout)

        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))

    raise RuntimeError(f"Cannot fetch feed after {attempts} attempts: {last_error}") from last_error


def fetch_xiaoyuzhou_feed(url: str, timeout: int = 120) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8")

    parser = _NextDataParser()
    parser.feed(page)
    if not parser.parts:
        raise RuntimeError("Xiaoyuzhou page did not contain __NEXT_DATA__")
    payload = json.loads("".join(parser.parts))
    podcast = payload["props"]["pageProps"]["podcast"]

    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = str(podcast.get("title") or "Xiaoyuzhou podcast")
    ET.SubElement(channel, "link").text = url
    ET.SubElement(channel, "description").text = str(podcast.get("description") or "")

    for episode in podcast.get("episodes") or []:
        eid = str(episode.get("eid") or "").strip()
        if not eid:
            continue
        item = ET.SubElement(channel, "item")
        # The native xyzfm RSS uses the bare Xiaoyuzhou episode ID as its GUID.
        # Preserve that identity so switching sources cannot create a phantom late episode.
        ET.SubElement(item, "guid").text = eid
        ET.SubElement(item, "title").text = str(episode.get("title") or "Untitled episode")
        episode_url = f"https://www.xiaoyuzhoufm.com/episode/{eid}"
        ET.SubElement(item, "link").text = episode_url
        published = episode.get("pubDate")
        if published:
            parsed = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            ET.SubElement(item, "pubDate").text = format_datetime(parsed)
        description = episode.get("shownotes") or episode.get("description") or ""
        ET.SubElement(item, "description").text = str(description)
        enclosure = episode.get("enclosure") or {}
        audio_url = enclosure.get("url") if isinstance(enclosure, dict) else None
        if audio_url:
            ET.SubElement(item, "enclosure", {"url": str(audio_url), "type": "audio/m4a"})
        duration = episode.get("duration")
        if duration is not None:
            ET.SubElement(item, f"{ITUNES_NS}duration").text = str(duration)

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def _text(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(xml_bytes: bytes, podcast_title: str, podcast_publisher: str) -> list[Episode]:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return []

    episodes: list[Episode] = []
    for item in channel.findall("item"):
        guid = _text(item, "guid") or _text(item, "link") or _text(item, "title")
        title = _text(item, "title") or "Untitled episode"
        pub_date = _parse_date(_text(item, "pubDate"))
        link = _text(item, "link")
        enclosure = item.find("enclosure")
        audio_url = enclosure.attrib.get("url") if enclosure is not None else None
        duration = _text(item, f"{ITUNES_NS}duration")
        transcript = item.find(f"{PODCAST_NS}transcript")
        transcript_url = transcript.attrib.get("url") if transcript is not None else None
        transcript_type = transcript.attrib.get("type") if transcript is not None else None
        description = (
            _text(item, f"{CONTENT_NS}encoded")
            or _text(item, "description")
            or _text(item, "summary")
            or ""
        )
        if not guid:
            continue
        episodes.append(
            Episode(
                podcast_title=podcast_title,
                podcast_publisher=podcast_publisher,
                guid=guid,
                title=title,
                published_at=pub_date,
                episode_url=link,
                audio_url=audio_url,
                duration=duration,
                description=_clean_html(description),
                transcript_url=transcript_url,
                transcript_type=transcript_type,
            )
        )
    return episodes


def cache_feed(path: Path, xml_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(xml_bytes)
