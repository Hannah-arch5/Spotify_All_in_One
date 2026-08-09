#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def render(manifest_path: Path) -> Path:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    report_path = ROOT / "reports" / "markdown" / f"{data['run_id']}-episode-list.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# 播客更新清单 {data['run_id']}",
        "",
        f"- 生成时间：{_format_time(data['created_at'])}",
        f"- 排序规则：{data['sort_rule']}（最新发布时间在前）",
        f"- 已配置播客：{data['summary']['configured_podcasts']}",
        f"- 已启用 RSS：{data['summary']['enabled_with_rss']}",
        f"- RSS 失败：{data['summary']['feed_failures']}",
        f"- 新增 episode：{data['summary']['new_episode_count']}",
        "",
        "## 新增 Episode",
        "",
    ]

    if not data["new_episodes"]:
        lines.append("本次没有发现新的 episode。")
    else:
        for index, episode in enumerate(data["new_episodes"], 1):
            lines.extend(
                [
                    f"### {index}. {episode['episode_title']}",
                    "",
                    f"- 播客：{episode['podcast_title']}",
                    f"- 发布时间：{_format_time(episode['published_at'])}",
                    f"- 时长：{episode['duration'] or 'unknown'}",
                    f"- 页面：{episode['episode_url'] or 'none'}",
                    f"- 音频：{episode['audio_url'] or 'none'}",
                    f"- Transcript：{episode['transcript_url'] or 'none'}",
                    f"- GUID：`{episode['guid']}`",
                    "",
                    episode["description_preview"] or "无简介。",
                    "",
                ]
            )

    problems = [podcast for podcast in data["podcasts"] if podcast["status"] not in {"ok", "excluded"}]
    if problems:
        lines.extend(["## 需要处理的源", ""])
        for podcast in problems:
            lines.append(f"- {podcast['title']}：{podcast['status']} {podcast.get('error', '')}".rstrip())
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a readable Markdown episode list.")
    parser.add_argument("manifest", nargs="?", type=Path, help="Manifest JSON path. Defaults to latest.")
    args = parser.parse_args()
    path = args.manifest or _latest_manifest()
    print(render(path))


if __name__ == "__main__":
    main()
