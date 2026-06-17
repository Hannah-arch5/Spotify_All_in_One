#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZH_DIR = ROOT / "data" / "transcripts" / "spotify_zh"


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("&", " and ")
    value = re.sub(r"[\u2018\u2019\u201c\u201d]", "'", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _similarity(left: str | None, right: str | None) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_time(value: str | None) -> str:
    if not value:
        return "unknown time"
    return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _zh_transcripts(chinese_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not chinese_dir.exists():
        return rows
    for path in sorted(chinese_dir.glob("*.json")):
        try:
            data = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        segments = data.get("segments")
        rows.append(
            {
                "path": str(path),
                "spotify_episode_id": data.get("spotifyEpisodeId"),
                "episode_url": data.get("episodeUrl"),
                "podcast_name": data.get("podcastName"),
                "episode_title": data.get("episodeTitle"),
                "published_date": data.get("publishedDate"),
                "language": data.get("transcriptLanguage"),
                "segments_count": len(segments) if isinstance(segments, list) else 0,
            }
        )
    return rows


def _score(episode: dict[str, object], transcript: dict[str, object]) -> float:
    episode_id = None
    transcript_meta = episode.get("transcript")
    if isinstance(transcript_meta, dict):
        episode_id = transcript_meta.get("spotify_episode_id")
    if episode_id and episode_id == transcript.get("spotify_episode_id"):
        return 1.0
    title_score = _similarity(str(episode.get("episode_title") or ""), str(transcript.get("episode_title") or ""))
    podcast_score = _similarity(str(episode.get("podcast_title") or ""), str(transcript.get("podcast_name") or ""))
    return title_score * 0.78 + podcast_score * 0.22


def _match_zh(episode: dict[str, object], transcripts: list[dict[str, object]]) -> dict[str, object] | None:
    scored = [(_score(episode, transcript), transcript) for transcript in transcripts]
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or scored[0][0] < 0.82:
        return None
    score, transcript = scored[0]
    return {"match_score": round(score, 3), **transcript}


def audit(evidence_pack_path: Path, chinese_dir: Path) -> tuple[Path, Path, dict[str, object]]:
    pack = _load_json(evidence_pack_path)
    zh_rows = _zh_transcripts(chinese_dir)
    rows = []
    for episode in pack["episodes"]:
        transcript = episode.get("transcript")
        en_ready = bool(transcript)
        zh_match = _match_zh(episode, zh_rows)
        rows.append(
            {
                "index": episode["index"],
                "podcast_title": episode["podcast_title"],
                "episode_title": episode["episode_title"],
                "published_at": episode["published_at"],
                "english_transcript": "found" if en_ready else "missing",
                "chinese_transcript": "found" if zh_match else "missing",
                "chinese_match": zh_match,
            }
        )

    missing_zh = [row for row in rows if row["chinese_transcript"] == "missing"]
    payload = {
        "run_id": pack["run_id"],
        "created_at": datetime.now().astimezone().isoformat(),
        "evidence_pack_path": str(evidence_pack_path),
        "chinese_transcript_dir": str(chinese_dir),
        "summary": {
            "episode_count": len(rows),
            "english_found_count": sum(1 for row in rows if row["english_transcript"] == "found"),
            "chinese_found_count": sum(1 for row in rows if row["chinese_transcript"] == "found"),
            "chinese_missing_count": len(missing_zh),
        },
        "episodes": rows,
    }

    output_json = ROOT / "data" / "runs" / f"{pack['run_id']}-transcript-language-audit.json"
    output_md = ROOT / "reports" / "markdown" / f"{pack['run_id']}-transcript-language-audit.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_md, payload)
    return output_json, output_md, payload


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    summary = payload["summary"]
    lines = [
        f"# Transcript 语言覆盖审计 {payload['run_id']}",
        "",
        f"- 生成时间：{_format_time(str(payload['created_at']))}",
        f"- Episode 数量：{summary['episode_count']}",
        f"- 英文/原文 transcript：{summary['english_found_count']}",
        f"- 中文 transcript：{summary['chinese_found_count']}",
        f"- 缺中文 transcript：{summary['chinese_missing_count']}",
        f"- 中文目录：`{payload['chinese_transcript_dir']}`",
        "",
        "## 明细",
        "",
    ]
    for row in payload["episodes"]:
        match = row.get("chinese_match")
        lines.extend(
            [
                f"### {row['index']}. {row['episode_title']}",
                "",
                f"- 播客：{row['podcast_title']}",
                f"- 发布时间：{_format_time(row['published_at'])}",
                f"- 英文/原文 transcript：`{row['english_transcript']}`",
                f"- 中文 transcript：`{row['chinese_transcript']}`",
            ]
        )
        if isinstance(match, dict):
            lines.extend(
                [
                    f"- 中文文件：`{match['path']}`",
                    f"- 匹配分数：{match['match_score']}",
                    f"- 字幕段落数：{match['segments_count']}",
                ]
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit English/original and Chinese transcript coverage for an evidence pack.")
    parser.add_argument("evidence_pack", type=Path)
    parser.add_argument("--chinese-dir", type=Path, default=DEFAULT_ZH_DIR)
    parser.add_argument("--require-zh", action="store_true", help="Exit non-zero when any episode lacks a Chinese transcript.")
    args = parser.parse_args()

    output_json, output_md, payload = audit(args.evidence_pack, args.chinese_dir)
    print(output_json)
    print(output_md)
    if args.require_zh and payload["summary"]["chinese_missing_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
