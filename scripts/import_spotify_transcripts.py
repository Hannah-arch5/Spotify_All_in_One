#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Downloads" / "Spotify Transcript Collector"
DEFAULT_TARGET_DIR = ROOT / "data" / "transcripts" / "spotify"


def _same_file_content(source_path: Path, target_path: Path) -> bool:
    return target_path.exists() and target_path.stat().st_size == source_path.stat().st_size


def import_transcripts(source_dir: Path, target_dir: Path, move: bool = False) -> tuple[int, int, int]:
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)
    imported = 0
    skipped = 0
    removed = 0

    for source_path in sorted(source_dir.glob("*.json")):
        target_path = target_dir / source_path.name
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

    return imported, skipped, removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Spotify transcript JSON files into the project.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    parser.add_argument(
        "--move",
        action="store_true",
        help="Delete source files from Downloads after they are verified in the project archive.",
    )
    args = parser.parse_args()

    imported, skipped, removed = import_transcripts(args.source_dir, args.target_dir, move=args.move)
    print(f"imported={imported} skipped={skipped} removed={removed} target={args.target_dir}")


if __name__ == "__main__":
    main()
