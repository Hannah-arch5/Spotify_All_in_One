#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
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

    for source_path in sorted(source_dir.glob("*.json")):
        is_zh = _is_chinese_translation(source_path)
        target_dir = chinese_dir if is_zh else english_dir
        target_path = target_dir / source_path.name
        if is_zh:
            chinese += 1
        else:
            english += 1
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
