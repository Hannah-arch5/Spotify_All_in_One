#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Podcast, load_podcasts
from src.rss import Episode, cache_feed, fetch_feed, parse_feed
from src.state import connect, mark_seen, seen_guids


def _safe_name(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{digest}.xml"


def _episode_to_dict(episode: Episode, is_new: bool) -> dict[str, object]:
    return {
        "podcast_title": episode.podcast_title,
        "podcast_publisher": episode.podcast_publisher,
        "episode_title": episode.title,
        "published_at": episode.published_at.isoformat() if episode.published_at else None,
        "guid": episode.guid,
        "episode_url": episode.episode_url,
        "audio_url": episode.audio_url,
        "duration": episode.duration,
        "transcript_url": episode.transcript_url,
        "transcript_type": episode.transcript_type,
        "is_new": is_new,
        "description_preview": episode.description[:500],
    }


def _podcast_status(podcast: Podcast, status: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": podcast.title,
        "publisher": podcast.publisher,
        "display_order": podcast.display_order,
        "priority": podcast.priority,
        "rss_url": podcast.rss_url,
        "status": status,
    }
    payload.update(extra)
    return payload


def run(args: argparse.Namespace) -> Path:
    podcasts = load_podcasts(ROOT / "config" / "podcasts.yaml")
    connection = connect(ROOT / "data" / "state.sqlite")
    already_seen = seen_guids(connection)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.since_days) if args.since_days else None

    statuses: list[dict[str, object]] = []
    all_candidates: list[Episode] = []
    failures = 0

    for podcast in podcasts:
        if podcast.priority == "exclude":
            statuses.append(_podcast_status(podcast, "excluded"))
            continue
        if not podcast.rss_url:
            statuses.append(_podcast_status(podcast, "missing_rss_url"))
            continue

        try:
            xml_bytes = fetch_feed(podcast.rss_url)
            cache_feed(ROOT / "data" / "feeds" / _safe_name(podcast.rss_url), xml_bytes)
            episodes = parse_feed(xml_bytes, podcast.title, podcast.publisher)
        except Exception as exc:
            failures += 1
            statuses.append(_podcast_status(podcast, "feed_error", error=str(exc)))
            continue

        windowed = [
            episode
            for episode in episodes
            if cutoff is None or episode.published_at is None or episode.published_at >= cutoff
        ]
        candidates = [episode for episode in windowed if episode.guid not in already_seen]
        all_candidates.extend(candidates)
        statuses.append(
            _podcast_status(
                podcast,
                "ok",
                feed_episode_count=len(episodes),
                in_window_count=len(windowed),
                new_count=len(candidates),
                latest_published_at=(
                    max(
                        (episode.published_at for episode in episodes if episode.published_at),
                        default=None,
                    ).isoformat()
                    if episodes
                    else None
                ),
            )
        )

    all_candidates.sort(
        key=lambda episode: episode.published_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    if args.mark_seen:
        mark_seen(connection, all_candidates)

    run_id = now.astimezone().strftime("%Y%m%d-%H%M%S")
    manifest = {
        "run_id": run_id,
        "created_at": now.isoformat(),
        "since_days": args.since_days,
        "marked_seen": args.mark_seen,
        "sort_rule": "episode.published_at desc",
        "summary": {
            "configured_podcasts": len(podcasts),
            "enabled_with_rss": sum(1 for podcast in podcasts if podcast.enabled),
            "missing_rss_url": sum(1 for status in statuses if status["status"] == "missing_rss_url"),
            "excluded": sum(1 for status in statuses if status["status"] == "excluded"),
            "feed_failures": failures,
            "new_episode_count": len(all_candidates),
        },
        "podcasts": statuses,
        "new_episodes": [_episode_to_dict(episode, True) for episode in all_candidates],
    }

    output_path = ROOT / "data" / "runs" / f"{run_id}-manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check podcast RSS feeds for new episodes.")
    parser.add_argument(
        "--since-days",
        type=int,
        default=3,
        help="Only consider episodes published within this many days. Use 0 for no date limit.",
    )
    parser.add_argument(
        "--mark-seen",
        action="store_true",
        help="Record discovered episodes in the local state database after writing the manifest.",
    )
    args = parser.parse_args()
    output_path = run(args)
    print(output_path)


if __name__ == "__main__":
    main()
