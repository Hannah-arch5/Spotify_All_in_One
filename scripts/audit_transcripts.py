#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_HINT_RE = re.compile(r"\b(transcript|transcription|read the transcript)\b", re.I)


def _latest_manifest() -> Path:
    manifests = sorted((ROOT / "data" / "runs").glob("*-manifest.json"))
    if not manifests:
        raise SystemExit("No manifest files found. Run scripts/check_new_episodes.py first.")
    return manifests[-1]


def _format_time(value: str | None) -> str:
    if not value:
        return "unknown time"
    dt = datetime.fromisoformat(value)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _classify(episode: dict[str, object]) -> tuple[str, str]:
    if episode.get("transcript_url"):
        return "rss_transcript", str(episode["transcript_url"])
    description = str(episode.get("description_preview") or "")
    if TRANSCRIPT_HINT_RE.search(description):
        return "transcript_hint_in_description", "简介中提到 transcript，需要打开 episode 页面提取。"
    if episode.get("audio_url"):
        return "needs_asr", "RSS 有音频 URL，可进入自动转写。"
    return "blocked", "没有 transcript，也没有音频 URL。"


def render(manifest_path: Path) -> Path:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    counts: dict[str, int] = {}
    for episode in data["new_episodes"]:
        status, detail = _classify(episode)
        counts[status] = counts.get(status, 0) + 1
        rows.append((status, detail, episode))

    output_path = ROOT / "reports" / "markdown" / f"{data['run_id']}-transcript-audit.md"
    lines = [
        f"# Transcript 可用性检查 {data['run_id']}",
        "",
        f"- 生成时间：{_format_time(data['created_at'])}",
        f"- Episode 数量：{len(data['new_episodes'])}",
        f"- RSS 自带 transcript：{counts.get('rss_transcript', 0)}",
        f"- 简介疑似 transcript：{counts.get('transcript_hint_in_description', 0)}",
        f"- 需要自动转写：{counts.get('needs_asr', 0)}",
        f"- 阻塞：{counts.get('blocked', 0)}",
        "",
        "## 明细",
        "",
    ]

    for index, (status, detail, episode) in enumerate(rows, 1):
        lines.extend(
            [
                f"### {index}. {episode['episode_title']}",
                "",
                f"- 播客：{episode['podcast_title']}",
                f"- 发布时间：{_format_time(episode['published_at'])}",
                f"- 状态：`{status}`",
                f"- 说明：{detail}",
                f"- 页面：{episode['episode_url'] or 'none'}",
                f"- 音频：{episode['audio_url'] or 'none'}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit transcript availability for a run manifest.")
    parser.add_argument("manifest", nargs="?", type=Path, help="Manifest JSON path. Defaults to latest.")
    args = parser.parse_args()
    print(render(args.manifest or _latest_manifest()))


if __name__ == "__main__":
    main()
