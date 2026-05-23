#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSCRIPT_DIR = ROOT / "data" / "transcripts" / "spotify"


def _parse_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _transcript_date(path: Path) -> datetime | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    for key in ("publishedDate", "capturedAt"):
        parsed = _parse_date(data.get(key))
        if parsed:
            return parsed
    return None


def prune(transcript_dir: Path, keep_days: int, dry_run: bool) -> tuple[int, int, int]:
    if not transcript_dir.exists():
        raise SystemExit(f"Transcript directory not found: {transcript_dir}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept = 0
    deleted = 0
    unknown = 0

    for path in sorted(transcript_dir.glob("*.json")):
        transcript_date = _transcript_date(path)
        if transcript_date is None:
            unknown += 1
            print(f"KEEP unknown-date {path}")
            continue
        if transcript_date >= cutoff:
            kept += 1
            continue

        deleted += 1
        action = "WOULD_DELETE" if dry_run else "DELETE"
        print(f"{action} {transcript_date.date()} {path}")
        if not dry_run:
            path.unlink()

    return kept, deleted, unknown


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune old archived Spotify transcript JSON files.")
    parser.add_argument("--transcript-dir", type=Path, default=DEFAULT_TRANSCRIPT_DIR)
    parser.add_argument("--keep-days", type=int, default=90)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete old files. Without this flag the script only previews.",
    )
    args = parser.parse_args()

    kept, deleted, unknown = prune(args.transcript_dir, args.keep_days, dry_run=not args.delete)
    mode = "deleted" if args.delete else "would_delete"
    print(f"kept={kept} {mode}={deleted} unknown_date_kept={unknown} keep_days={args.keep_days}")


if __name__ == "__main__":
    main()
