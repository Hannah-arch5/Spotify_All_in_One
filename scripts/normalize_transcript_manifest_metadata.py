#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from import_official_vtt_transcript import ROOT, clean_filename


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(data: dict[str, object]) -> str | None:
    spotify_id = str(data.get("spotifyEpisodeId") or "").strip()
    if spotify_id:
        return spotify_id
    source_id = str(data.get("sourceEpisodeId") or "").strip()
    return source_id or None


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize transcript metadata to a fixed report manifest.")
    parser.add_argument("evidence_pack", type=Path)
    parser.add_argument("--chinese-dir", type=Path, default=ROOT / "data" / "transcripts" / "spotify_zh")
    args = parser.parse_args()

    evidence = load_json(args.evidence_pack)
    chinese_by_id: dict[str, list[tuple[Path, dict[str, object]]]] = {}
    for path in args.chinese_dir.glob("*.json"):
        data = load_json(path)
        item_id = identity(data)
        if item_id:
            chinese_by_id.setdefault(item_id, []).append((path, data))

    normalized_originals = 0
    normalized_chinese = 0
    for item in evidence.get("episodes") or []:
        transcript = item.get("transcript") or {}
        source_path_value = transcript.get("path")
        if not source_path_value:
            continue
        source_path = Path(str(source_path_value))
        source = load_json(source_path)
        item_id = identity(source)
        if not item_id:
            raise SystemExit(f"Transcript has no stable identity: {source_path}")
        published_date = str(item.get("published_at") or "")[:10]
        source["episodeTitle"] = item.get("episode_title")
        source["podcastName"] = item.get("podcast_title")
        source["publishedDate"] = published_date
        if source.get("spotifyEpisodeId"):
            source["episodeUrl"] = f"https://open.spotify.com/episode/{source['spotifyEpisodeId']}"
        write_json(source_path, source)
        source_hash = sha256(source_path)
        normalized_originals += 1

        matches = chinese_by_id.get(item_id, [])
        if len(matches) != 1:
            raise SystemExit(f"Expected one Chinese transcript for {item_id}, found {len(matches)}.")
        chinese_path, chinese = matches[0]
        chinese["episodeTitle"] = item.get("episode_title")
        chinese["podcastName"] = item.get("podcast_title")
        chinese["publishedDate"] = published_date
        chinese["episodeUrl"] = source.get("episodeUrl")
        chinese["sourceTranscriptSha256"] = source_hash
        suffix = clean_filename(item_id.replace(":", "_"))
        target = args.chinese_dir / (
            f"{published_date} - {clean_filename(item.get('podcast_title'))} - "
            f"{clean_filename(item.get('episode_title'))}_zh - {suffix}.json"
        )
        if target != chinese_path and target.exists():
            raise SystemExit(f"Refusing to overwrite duplicate Chinese transcript: {target}")
        write_json(chinese_path, chinese)
        if target != chinese_path:
            chinese_path.rename(target)
        normalized_chinese += 1

    print(f"originals={normalized_originals} chinese={normalized_chinese}")


if __name__ == "__main__":
    main()
