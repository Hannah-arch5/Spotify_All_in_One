from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Podcast:
    display_order: int
    title: str
    publisher: str
    language: str
    priority: str
    rss_url: str | None
    spotify_url: str | None
    notes: str

    @property
    def enabled(self) -> bool:
        return self.priority != "exclude" and bool(self.rss_url)


def _parse_value(raw: str) -> str | int | None:
    value = raw.strip()
    if value == "null":
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.isdigit():
        return int(value)
    return value


def load_podcasts(path: Path) -> list[Podcast]:
    """Parse the small YAML subset used by config/podcasts.yaml.

    This avoids adding package dependencies before the workflow shape is stable.
    """
    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "podcasts:":
            continue
        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        current[key.strip()] = _parse_value(raw_value)

    if current:
        items.append(current)

    podcasts: list[Podcast] = []
    for item in items:
        podcasts.append(
            Podcast(
                display_order=int(item["display_order"]),
                title=str(item["title"]),
                publisher=str(item["publisher"]),
                language=str(item["language"]),
                priority=str(item["priority"]),
                rss_url=item.get("rss_url") if item.get("rss_url") else None,
                spotify_url=item.get("spotify_url") if item.get("spotify_url") else None,
                notes=str(item.get("notes") or ""),
            )
        )
    return podcasts
