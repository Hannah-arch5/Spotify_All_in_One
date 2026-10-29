#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOWNLOAD = Path.home() / "Downloads" / "download.json"
DEFAULT_ARCHIVE = ROOT / "data" / "transcripts" / "spotify_en"


def clean_filename(value: object) -> str:
    return re.sub(r'[\\/:*?"<>|#%]', "_", str(value or "unknown")).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: object) -> str:
    return re.sub(r"\W+", "", str(value or "").casefold(), flags=re.UNICODE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify and archive one generic STD download before the next capture.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True, help="One-based episode index in the manifest.")
    parser.add_argument("--spotify-id", required=True, help="Episode ID verified on the open Spotify detail page.")
    parser.add_argument("--download", type=Path, default=DEFAULT_DOWNLOAD)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    episodes = manifest.get("new_episodes") or manifest.get("episodes") or []
    if args.index < 1 or args.index > len(episodes):
        raise SystemExit(f"Episode index {args.index} is outside 1..{len(episodes)}.")
    episode = episodes[args.index - 1]

    if not args.download.is_file():
        raise SystemExit(f"STD download not found: {args.download}")
    payload = json.loads(args.download.read_text(encoding="utf-8"))
    actual_id = str(payload.get("spotifyEpisodeId") or "").strip()
    if actual_id != args.spotify_id:
        raise SystemExit(f"Spotify ID mismatch: page={args.spotify_id} download={actual_id or 'missing'}")

    expected_title = str(episode.get("episode_title") or "").strip()
    actual_title = str(payload.get("episodeTitle") or "").strip()
    if normalized(expected_title) != normalized(actual_title):
        raise SystemExit(f"Episode title mismatch: manifest={expected_title!r} download={actual_title!r}")

    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise SystemExit("STD download contains no transcript segments.")
    if any(not isinstance(row, dict) or not str(row.get("text") or "").strip() for row in segments):
        raise SystemExit("STD download contains an empty or malformed transcript segment.")

    published_date = str(episode.get("published_at") or "")[:10]
    if not published_date:
        raise SystemExit("Manifest episode has no publication date.")
    payload["publishedDate"] = published_date
    payload["spotifyEpisodeId"] = actual_id
    payload["episodeUrl"] = f"https://open.spotify.com/episode/{actual_id}"

    filename = (
        f"{published_date} - {clean_filename(episode.get('podcast_title'))} - "
        f"{clean_filename(expected_title)} - {actual_id}.json"
    )
    args.archive.mkdir(parents=True, exist_ok=True)
    target = args.archive / filename
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing != rendered:
            raise SystemExit(f"Archive target already exists with different content; refusing overwrite: {target}")
    else:
        target.write_text(rendered, encoding="utf-8")
    target_hash = sha256(target)
    if not target_hash:
        raise RuntimeError(f"Archive hash verification failed: {target}")

    episode["spotify_episode_id"] = actual_id
    episode["spotify_episode_url"] = f"https://open.spotify.com/episode/{actual_id}"
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    args.download.unlink()

    print(
        json.dumps(
            {
                "index": args.index,
                "spotify_episode_id": actual_id,
                "segments": len(segments),
                "archive_path": str(target),
                "archive_sha256": target_hash,
                "download_removed": not args.download.exists(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
