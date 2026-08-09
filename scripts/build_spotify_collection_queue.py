#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]


def _latest_evidence_pack() -> Path:
    packs = sorted((ROOT / "data" / "runs").glob("*-evidence-pack.json"))
    if not packs:
        raise SystemExit("No evidence pack found. Run scripts/build_evidence_pack.py first.")
    return packs[-1]


def _format_time(value: str | None) -> str:
    if not value:
        return "unknown time"
    dt = datetime.fromisoformat(value)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _spotify_search_url(episode: dict[str, object]) -> str:
    query = f"{episode['podcast_title']} {episode['episode_title']}"
    return f"https://open.spotify.com/search/{quote(query)}/episodes"


def build(evidence_pack_path: Path) -> tuple[Path, Path]:
    pack = json.loads(evidence_pack_path.read_text(encoding="utf-8"))
    queue = []
    for episode in pack["episodes"]:
        if episode["status"] == "ready":
            continue
        queue.append(
            {
                "index": episode["index"],
                "podcast_title": episode["podcast_title"],
                "episode_title": episode["episode_title"],
                "published_at": episode["published_at"],
                "rss_episode_url": episode["rss_episode_url"],
                "audio_url": episode["audio_url"],
                "guid": episode["guid"],
                "spotify_search_url": _spotify_search_url(episode),
                "status": "needs_spotify_transcript",
            }
        )

    payload = {
        "run_id": pack["run_id"],
        "created_at": datetime.now().astimezone().isoformat(),
        "evidence_pack_path": str(evidence_pack_path),
        "ready_count": pack["summary"]["matched_count"],
        "queue_count": len(queue),
        "items": queue,
    }

    output_json = ROOT / "data" / "runs" / f"{pack['run_id']}-spotify-collection-queue.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    output_md = ROOT / "reports" / "markdown" / f"{pack['run_id']}-spotify-collection-queue.md"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(output_md, payload)
    return output_json, output_md


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        f"# Spotify Transcript 采集队列 {payload['run_id']}",
        "",
        f"- 生成时间：{_format_time(str(payload['created_at']))}",
        f"- 已有 transcript：{payload['ready_count']}",
        f"- 待采集：{payload['queue_count']}",
        "",
        "## 队列",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"### {item['index']}. {item['episode_title']}",
                "",
                f"- 播客：{item['podcast_title']}",
                f"- 发布时间：{_format_time(item['published_at'])}",
                f"- Spotify 搜索：{item['spotify_search_url']}",
                f"- RSS 页面：{item['rss_episode_url'] or 'none'}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Spotify transcript collection queue.")
    parser.add_argument("evidence_pack", nargs="?", type=Path, help="Evidence pack JSON path. Defaults to latest.")
    args = parser.parse_args()
    output_json, output_md = build(args.evidence_pack or _latest_evidence_pack())
    print(output_json)
    print(output_md)


if __name__ == "__main__":
    main()
