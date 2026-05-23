#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path.home() / "Downloads" / "Spotify Transcript Collector"
DEFAULT_TARGET_DIR = ROOT / "data" / "transcripts" / "spotify"


def import_transcripts(source_dir: Path, target_dir: Path) -> tuple[int, int]:
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0

    for source_path in sorted(source_dir.glob("*.json")):
        target_path = target_dir / source_path.name
        if target_path.exists() and target_path.stat().st_size == source_path.stat().st_size:
            skipped += 1
            continue
        shutil.copy2(source_path, target_path)
        copied += 1

    return copied, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Spotify transcript JSON files into the project.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    args = parser.parse_args()

    copied, skipped = import_transcripts(args.source_dir, args.target_dir)
    print(f"copied={copied} skipped={skipped} target={args.target_dir}")


if __name__ == "__main__":
    main()
