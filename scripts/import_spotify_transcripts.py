#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Downloads" / "Spotify Transcript Collector"
DEFAULT_EN_DIR = ROOT / "data" / "transcripts" / "spotify_en"
DEFAULT_ZH_DIR = ROOT / "data" / "transcripts" / "spotify_zh"


def _same_file_content(source_path: Path, target_path: Path) -> bool:
    return target_path.exists() and target_path.stat().st_size == source_path.stat().st_size


def _is_chinese_translation(path: Path) -> bool:
    if "_zh" in path.stem:
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    segments = data.get("segments")
    if not isinstance(segments, list):
        return False
    return any(isinstance(segment, dict) and segment.get("translation") for segment in segments)


def _load_transcript(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_complete_chinese(path: Path, data: dict) -> bool:
    if "_zh_incomplete" in path.stem.casefold():
        return False
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return False
    return not any(
        isinstance(segment, dict) and segment.get("text") and not segment.get("translation")
        for segment in segments
    )


def _identity(path: Path, data: dict, language: str) -> tuple[str, str]:
    episode_id = str(data.get("spotifyEpisodeId") or "").strip()
    if not episode_id:
        episode_id = "|".join(
            [
                str(data.get("podcastName") or "").strip().casefold(),
                str(data.get("episodeTitle") or "").strip().casefold(),
            ]
        )
    return episode_id or path.stem.casefold(), language


def _canonical_name(path: Path) -> str:
    return re.sub(r"\s+\(\d+\)(?=\.json$)", "", path.name)


def _candidate_score(path: Path, data: dict) -> tuple[int, int, float]:
    segments = data.get("segments")
    segment_count = len(segments) if isinstance(segments, list) else 0
    duplicate_suffix = bool(re.search(r"\s+\(\d+\)\.json$", path.name))
    return (0 if duplicate_suffix else 1, segment_count, path.stat().st_mtime)


def import_transcripts(
    source_dir: Path,
    english_dir: Path,
    chinese_dir: Path,
    move: bool = False,
) -> tuple[int, int, int, int, int]:
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")

    english_dir.mkdir(parents=True, exist_ok=True)
    chinese_dir.mkdir(parents=True, exist_ok=True)
    imported = 0
    skipped = 0
    removed = 0
    english = 0
    chinese = 0

    source_rows: list[tuple[Path, dict, str, bool]] = []
    selected: dict[tuple[str, str], tuple[Path, dict, str, bool]] = {}
    for source_path in sorted(source_dir.glob("*.json")):
        try:
            data = _load_transcript(source_path)
        except (OSError, json.JSONDecodeError):
            source_rows.append((source_path, {}, "invalid", False))
            continue
        is_zh = _is_chinese_translation(source_path)
        language = "zh" if is_zh else "en"
        is_valid = not is_zh or _is_complete_chinese(source_path, data)
        row = (source_path, data, language, is_valid)
        source_rows.append(row)
        if not is_valid:
            continue
        key = _identity(source_path, data, language)
        current = selected.get(key)
        if current is None or _candidate_score(source_path, data) > _candidate_score(current[0], current[1]):
            selected[key] = row

    selected_paths = {row[0] for row in selected.values()}
    english = sum(1 for row in selected.values() if row[2] == "en")
    chinese = sum(1 for row in selected.values() if row[2] == "zh")

    for source_path, _, language, is_valid in source_rows:
        if not is_valid or source_path not in selected_paths:
            skipped += 1
            if move:
                source_path.unlink()
                removed += 1
            continue

        target_dir = chinese_dir if language == "zh" else english_dir
        target_path = target_dir / _canonical_name(source_path)
        if _same_file_content(source_path, target_path):
            skipped += 1
            if move:
                source_path.unlink()
                removed += 1
            continue

        shutil.copy2(source_path, target_path)
        if not _same_file_content(source_path, target_path):
            raise RuntimeError(f"Copied file failed verification: {source_path}")
        imported += 1
        if move:
            source_path.unlink()
            removed += 1

    return imported, skipped, removed, english, chinese


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Spotify transcript JSON files into the project.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--english-dir", type=Path, default=DEFAULT_EN_DIR)
    parser.add_argument("--chinese-dir", type=Path, default=DEFAULT_ZH_DIR)
    parser.add_argument(
        "--move",
        action="store_true",
        help="Delete source files from Downloads after they are verified in the project archive.",
    )
    args = parser.parse_args()

    imported, skipped, removed, english, chinese = import_transcripts(
        args.source_dir,
        args.english_dir,
        args.chinese_dir,
        move=args.move,
    )
    print(
        " ".join(
            [
                f"imported={imported}",
                f"skipped={skipped}",
                f"removed={removed}",
                f"english_seen={english}",
                f"chinese_seen={chinese}",
                f"english_dir={args.english_dir}",
                f"chinese_dir={args.chinese_dir}",
            ]
        )
    )


if __name__ == "__main__":
    main()
