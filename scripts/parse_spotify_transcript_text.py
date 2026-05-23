#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")
SPEAKER_RE = re.compile(r"^Speaker\s+\d+$", re.I)


def parse_time(value: str) -> float:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def parse_transcript(text: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    active_speaker: str | None = None

    for line in lines:
        if line == "Transcript" or line.startswith("This transcript was generated automatically"):
            continue
        if SPEAKER_RE.match(line):
            active_speaker = line
            if current and not current.get("speaker"):
                current["speaker"] = active_speaker
            continue
        if TIME_RE.match(line):
            if current:
                current["text"] = " ".join(current["text"]).strip()
                if current["text"]:
                    segments.append(current)
            current = {
                "start": parse_time(line),
                "timestamp": line,
                "speaker": active_speaker,
                "text": [],
            }
            continue
        if current is None:
            continue
        current["text"].append(line)

    if current:
        current["text"] = " ".join(current["text"]).strip()
        if current["text"]:
            segments.append(current)

    for index, segment in enumerate(segments[:-1]):
        segment["end"] = segments[index + 1]["start"]
    if segments:
        segments[-1]["end"] = None
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse copied Spotify transcript text into JSON segments.")
    parser.add_argument("input", type=Path, help="Plain text transcript copied from Spotify.")
    parser.add_argument("output", type=Path, help="Output JSON path.")
    parser.add_argument("--episode-url", default=None)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    segments = parse_transcript(text)
    payload = {
        "source": "spotify_dom_transcript",
        "episodeUrl": args.episode_url,
        "title": args.title,
        "segmentCount": len(segments),
        "segments": segments,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
