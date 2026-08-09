from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .rss import Episode


SCHEMA = """
create table if not exists processed_episodes (
  guid text primary key,
  podcast_title text not null,
  episode_title text not null,
  published_at text,
  first_seen_at text not null,
  audio_url text,
  episode_url text
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(SCHEMA)
    return connection


def seen_guids(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("select guid from processed_episodes").fetchall()
    return {row[0] for row in rows}


def mark_seen(connection: sqlite3.Connection, episodes: list[Episode]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            episode.guid,
            episode.podcast_title,
            episode.title,
            episode.published_at.isoformat() if episode.published_at else None,
            now,
            episode.audio_url,
            episode.episode_url,
        )
        for episode in episodes
    ]
    connection.executemany(
        """
        insert or ignore into processed_episodes
          (guid, podcast_title, episode_title, published_at, first_seen_at, audio_url, episode_url)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
