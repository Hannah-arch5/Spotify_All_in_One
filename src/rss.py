from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
import re
import xml.etree.ElementTree as ET


ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
PODCAST_NS = "{https://podcastindex.org/namespace/1.0}"


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


def fetch_feed(url: str, timeout: int = 30) -> bytes:
    request = Request(url, headers={"User-Agent": "Spotify-All-in-One/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except URLError as exc:
        raise RuntimeError(f"Cannot fetch feed: {exc}") from exc


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
