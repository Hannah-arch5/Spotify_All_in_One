#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.state import connect, mark_seen


@dataclass
class ManifestEpisode:
    guid: str
    podcast_title: str
    title: str
    published_at: datetime | None
    audio_url: str | None
    episode_url: str | None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _episodes_from_manifest(path: Path) -> list[ManifestEpisode]:
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = []
    for episode in data.get("new_episodes") or []:
        episodes.append(
            ManifestEpisode(
                guid=str(episode["guid"]),
                podcast_title=str(episode["podcast_title"]),
                title=str(episode["episode_title"]),
                published_at=_parse_datetime(episode.get("published_at")),
                audio_url=episode.get("audio_url"),
                episode_url=episode.get("episode_url"),
            )
        )
    return episodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark the episodes in a manifest as processed in data/state.sqlite.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--state-db", type=Path, default=ROOT / "data" / "state.sqlite")
    args = parser.parse_args()

    episodes = _episodes_from_manifest(args.manifest)
    connection = connect(args.state_db)
    try:
        mark_seen(connection, episodes)  # type: ignore[arg-type]
    finally:
        connection.close()
    print(f"marked_seen={len(episodes)} manifest={args.manifest}")


if __name__ == "__main__":
    main()
