#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import unicodedata

from import_official_vtt_transcript import ROOT, clean_filename


def normalized(value: object) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify one generic STD download before archiving it.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--spotify-id", required=True)
    parser.add_argument("--download", type=Path, default=Path.home() / "Downloads" / "download.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "transcripts" / "spotify_en")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    episodes = manifest.get("new_episodes") or []
    if not 1 <= args.index <= len(episodes):
        raise SystemExit(f"Episode index {args.index} is outside 1..{len(episodes)}.")
    episode = episodes[args.index - 1]
    data = json.loads(args.download.read_text(encoding="utf-8"))
    if str(data.get("spotifyEpisodeId") or "") != args.spotify_id:
        raise SystemExit("STD download episode ID does not match the verified Spotify detail page.")
    if normalized(data.get("episodeTitle")) != normalized(episode.get("episode_title")):
        raise SystemExit("STD download title does not match this manifest episode; review manually.")
    rss_show = normalized(episode.get("podcast_title"))
    spotify_show = normalized(data.get("podcastName"))
    if rss_show != spotify_show and not spotify_show.startswith(f"{rss_show} "):
        raise SystemExit("STD download podcast does not match this manifest episode; review manually.")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise SystemExit("STD download has no transcript segments.")
    if any(isinstance(segment, dict) and segment.get("translation") for segment in segments):
        raise SystemExit("STD download includes translations; this importer only accepts original speech.")

    published_date = str(episode.get("published_at") or "")[:10]
    target = args.out_dir / (
        f"{published_date} - {clean_filename(episode.get('podcast_title'))} - "
        f"{clean_filename(episode.get('episode_title'))} - {args.spotify_id}.json"
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in args.out_dir.glob(f"* - {args.spotify_id}.json") if path != target]
    if existing:
        raise SystemExit(f"An archive for this Spotify episode ID already exists: {existing[0]}")
    if target.exists():
        if sha256(target) != sha256(args.download):
            raise SystemExit("An archive with this identity already exists but has different content.")
    else:
        shutil.copy2(args.download, target)
    if sha256(target) != sha256(args.download):
        raise SystemExit("Archive copy failed SHA-256 verification; download was retained.")
    args.download.unlink()
    print(f"path={target}")
    print(f"spotify_id={args.spotify_id} segments={len(segments)} sha256={sha256(target)} download_removed=true")


if __name__ == "__main__":
    main()
