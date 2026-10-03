#!/usr/bin/env python3
"""Recover a fixed report-window manifest from the late-RSS audit record."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _parse(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    since, until = _parse(args.since), _parse(args.until)
    selected = [
        item
        for item in audit["late_unprocessed"]
        if item.get("expected_window", {}).get("since") == args.since
        and item.get("expected_window", {}).get("until") == args.until
    ]
    selected.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    if not selected:
        raise SystemExit("no audit episodes matched the requested window")

    by_podcast: dict[str, dict[str, object]] = {}
    episodes: list[dict[str, object]] = []
    for item in selected:
        title = item["podcast_title"]
        by_podcast.setdefault(
            title,
            {
                "title": title,
                "publisher": item.get("podcast_publisher"),
                "status": "recovered_from_late_rss_audit",
            },
        )
        episodes.append(
            {
                "podcast_title": title,
                "podcast_publisher": item.get("podcast_publisher"),
                "episode_title": item["title"],
                "published_at": item.get("published_at"),
                "guid": item["guid"],
                "episode_url": item.get("episode_url"),
                "audio_url": item.get("audio_url"),
                "duration": item.get("duration"),
                "transcript_url": item.get("transcript_url"),
                "transcript_type": item.get("transcript_type"),
                "is_new": True,
                "description_preview": (item.get("description") or "")[:500],
            }
        )

    now = datetime.now(timezone.utc)
    manifest = {
        "run_id": args.run_id,
        "created_at": now.isoformat(),
        "since_days": 3,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "marked_seen": False,
        "sort_rule": "episode.published_at desc",
        "summary": {
            "configured_podcasts": len(by_podcast),
            "enabled_with_rss": len(by_podcast),
            "missing_rss_url": 0,
            "excluded": 0,
            "feed_failures": 0,
            "new_episode_count": len(episodes),
            "recovered_from_late_rss_audit": True,
        },
        "podcasts": list(by_podcast.values()),
        "new_episodes": episodes,
    }
    output = ROOT / "data" / "runs" / f"{args.run_id}-manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
