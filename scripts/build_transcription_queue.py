#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _latest_manifest() -> Path:
    manifests = sorted((ROOT / "data" / "runs").glob("*-manifest.json"))
    if not manifests:
        raise SystemExit("No manifest files found. Run scripts/check_new_episodes.py first.")
    return manifests[-1]


def _slug(value: str) -> str:
    asciiish = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{asciiish[:60] or 'episode'}-{digest}"


def build(manifest_path: Path) -> Path:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    queue = []

    for episode in data["new_episodes"]:
        if episode.get("transcript_url"):
            continue
        if not episode.get("audio_url"):
            continue

        episode_id = _slug(f"{episode['podcast_title']} {episode['guid']}")
        description = str(episode.get("description_preview") or "")
        has_transcript_hint = bool(re.search(r"\b(transcript|transcription|read the transcript)\b", description, re.I))
        queue.append(
            {
                "episode_id": episode_id,
                "podcast_title": episode["podcast_title"],
                "episode_title": episode["episode_title"],
                "published_at": episode["published_at"],
                "guid": episode["guid"],
                "episode_url": episode["episode_url"],
                "audio_url": episode["audio_url"],
                "duration": episode["duration"],
                "transcript_output": f"data/transcripts/{episode_id}.json",
                "preferred_method": "fetch_page_transcript_then_asr" if has_transcript_hint else "asr",
                "status": "queued",
            }
        )

    output_path = ROOT / "data" / "runs" / f"{data['run_id']}-transcription-queue.json"
    output_path.write_text(
        json.dumps(
            {
                "run_id": data["run_id"],
                "source_manifest": str(manifest_path),
                "queue_count": len(queue),
                "items": queue,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an ASR transcription queue from a run manifest.")
    parser.add_argument("manifest", nargs="?", type=Path, help="Manifest JSON path. Defaults to latest.")
    args = parser.parse_args()
    print(build(args.manifest or _latest_manifest()))


if __name__ == "__main__":
    main()
