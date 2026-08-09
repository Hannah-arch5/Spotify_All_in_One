#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_podcasts
from src.rss import Episode, fetch_feed, parse_feed
from src.schedule import previous_report_cutoff
from src.state import connect, seen_guids


def _safe_name(value: str) -> str:
    return f"{hashlib.sha1(value.encode('utf-8')).hexdigest()[:10]}.xml"


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _manifest_guids(paths: list[Path] | None = None) -> set[str]:
    guids: set[str] = set()
    selected = paths if paths is not None else list((ROOT / "data" / "runs").glob("*-manifest.json"))
    for path in selected:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for episode in data.get("new_episodes") or []:
            guid = episode.get("guid")
            if guid:
                guids.add(str(guid))
    return guids


def _episode_to_dict(episode: Episode, window_since: datetime, window_until: datetime) -> dict[str, object]:
    payload = asdict(episode)
    payload["published_at"] = episode.published_at.isoformat() if episode.published_at else None
    payload["expected_window"] = {
        "since": window_since.isoformat(),
        "until": window_until.isoformat(),
    }
    return payload


def _write_episode_list(path: Path, payload: dict[str, object]) -> None:
    lines = [
        f"# Late RSS Arrival Audit {payload['created_at']}",
        "",
        f"- Since: `{payload['since']}`",
        f"- Until: `{payload['until']}`",
        f"- Feed failures: `{payload['summary']['feed_failures']}`",
        f"- Late/unprocessed episodes: `{payload['summary']['late_unprocessed_count']}`",
        "",
    ]
    if payload["late_unprocessed"]:
        lines.extend(["## Episodes", ""])
    for index, episode in enumerate(payload["late_unprocessed"], 1):
        lines.extend(
            [
                f"### {index}. {episode['title']}",
                "",
                f"- Podcast: {episode['podcast_title']}",
                f"- Published: `{episode['published_at']}`",
                f"- Expected window: `{episode['expected_window']['since']}` to `{episode['expected_window']['until']}`",
                f"- GUID: `{episode['guid']}`",
                f"- Episode URL: {episode['episode_url'] or 'none'}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def audit(args: argparse.Namespace) -> tuple[Path, Path, dict[str, object]]:
    since = _parse_datetime(args.since)
    until = _parse_datetime(args.until)
    if since >= until:
        raise SystemExit("--since must be earlier than --until")

    connection = connect(ROOT / "data" / "state.sqlite")
    seen = seen_guids(connection)
    ever_manifested = _manifest_guids()
    allowed_unseen = _manifest_guids(args.allowed_manifest) if args.allowed_manifest else set()
    podcasts = load_podcasts(ROOT / "config" / "podcasts.yaml")

    failures: list[dict[str, str]] = []
    cached_fallbacks: list[dict[str, str]] = []
    late_unprocessed: list[dict[str, object]] = []
    all_windowed = 0

    for podcast in podcasts:
        if podcast.priority == "exclude" or not podcast.rss_url:
            continue
        try:
            xml_bytes = fetch_feed(podcast.rss_url)
            episodes = parse_feed(xml_bytes, podcast.title, podcast.publisher)
        except Exception as exc:
            cache_path = ROOT / "data" / "feeds" / _safe_name(podcast.rss_url)
            try:
                age_seconds = datetime.now(timezone.utc).timestamp() - cache_path.stat().st_mtime
                if age_seconds > 3600:
                    raise RuntimeError(f"cached feed is stale: age_seconds={age_seconds:.0f}")
                episodes = parse_feed(cache_path.read_bytes(), podcast.title, podcast.publisher)
                cached_fallbacks.append(
                    {
                        "podcast": podcast.title,
                        "rss_url": podcast.rss_url,
                        "cache_path": str(cache_path),
                        "live_error": str(exc),
                        "cache_age_seconds": f"{age_seconds:.0f}",
                    }
                )
            except Exception as cache_exc:
                failures.append(
                    {
                        "podcast": podcast.title,
                        "rss_url": podcast.rss_url,
                        "error": str(exc),
                        "cache_error": str(cache_exc),
                    }
                )
                continue

        for episode in episodes:
            if episode.published_at is None:
                continue
            published = episode.published_at.astimezone(timezone.utc)
            if not (since <= published < until):
                continue
            all_windowed += 1
            if episode.guid in seen or episode.guid in allowed_unseen:
                continue
            window_until = until
            while previous_report_cutoff(window_until) > published:
                window_until = previous_report_cutoff(window_until)
            window_since = previous_report_cutoff(window_until)
            row = _episode_to_dict(episode, window_since, window_until)
            row["ever_manifested"] = episode.guid in ever_manifested
            late_unprocessed.append(row)

    late_unprocessed.sort(key=lambda row: row.get("published_at") or "", reverse=True)
    created_at = datetime.now(timezone.utc).astimezone().isoformat()
    run_id = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S-%f")
    payload = {
        "run_id": run_id,
        "created_at": created_at,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "summary": {
            "configured_podcasts": len(podcasts),
            "windowed_current_rss_episode_count": all_windowed,
            "feed_failures": len(failures),
            "feed_cached_fallbacks": len(cached_fallbacks),
            "late_unprocessed_count": len(late_unprocessed),
        },
        "feed_failures": failures,
        "feed_cached_fallbacks": cached_fallbacks,
        "late_unprocessed": late_unprocessed,
    }

    json_path = ROOT / "data" / "runs" / f"{run_id}-late-rss-arrivals-audit.json"
    md_path = ROOT / "reports" / "markdown" / f"{run_id}-late-rss-arrivals-audit.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_episode_list(md_path, payload)
    return json_path, md_path, payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit current RSS feeds for episodes published in past report windows but never manifested or marked seen."
    )
    parser.add_argument("--since", required=True, help="Inclusive lower publish-time bound as ISO datetime.")
    parser.add_argument("--until", required=True, help="Exclusive upper publish-time bound as ISO datetime.")
    parser.add_argument(
        "--allowed-manifest",
        action="append",
        type=Path,
        default=[],
        help="Manifest whose unseen episodes are intentionally being processed in this run.",
    )
    parser.add_argument("--require-clean", action="store_true", help="Exit non-zero if any late/unprocessed episode exists.")
    args = parser.parse_args()
    json_path, md_path, payload = audit(args)
    print(json_path)
    print(md_path)
    if args.require_clean and payload["summary"]["late_unprocessed_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
