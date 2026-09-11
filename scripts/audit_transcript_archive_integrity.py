#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_ids(evidence_path: Path) -> tuple[list[str], int]:
    pack = read_json(evidence_path)
    episodes = pack.get("episodes", [])
    values: list[str] = []
    for episode in episodes:
        transcript = episode.get("transcript") or {}
        episode_id = transcript.get("spotify_episode_id")
        if episode_id:
            values.append(str(episode_id))
    return values, len(episodes)


def inventory(directory: Path, *, chinese: bool) -> dict[str, list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(directory.glob("*.json")):
        try:
            data = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        episode_id = data.get("spotifyEpisodeId")
        if not episode_id:
            continue
        segments = data.get("segments") if isinstance(data.get("segments"), list) else []
        missing_translations = 0
        if chinese:
            missing_translations = sum(
                1
                for segment in segments
                if isinstance(segment, dict)
                and str(segment.get("text") or "").strip()
                and not str(segment.get("translation") or "").strip()
            )
        by_id[str(episode_id)].append(
            {
                "path": str(path),
                "segments": len(segments),
                "missing_translation_segments": missing_translations,
                "incomplete_filename": "_zh_incomplete" in path.stem.casefold(),
            }
        )
    return by_id


def language_result(
    ids: list[str], directory: Path, *, chinese: bool
) -> dict[str, Any]:
    rows = inventory(directory, chinese=chinese)
    expected = set(ids)
    missing = sorted(episode_id for episode_id in expected if not rows.get(episode_id))
    duplicates = {
        episode_id: items
        for episode_id, items in rows.items()
        if episode_id in expected and len(items) > 1
    }
    incomplete = {
        episode_id: items
        for episode_id, items in rows.items()
        if episode_id in expected
        and any(
            item["incomplete_filename"] or item["missing_translation_segments"]
            for item in items
        )
    }
    return {
        "directory": str(directory),
        "expected_ids": len(expected),
        "found_ids": len(expected - set(missing)),
        "missing_ids": missing,
        "duplicate_ids": duplicates,
        "incomplete_ids": incomplete,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Require one original and one complete Chinese transcript per evidence-pack episode."
    )
    parser.add_argument("evidence_pack", type=Path)
    parser.add_argument("--english-dir", type=Path, default=ROOT / "data/transcripts/spotify_en")
    parser.add_argument("--chinese-dir", type=Path, default=ROOT / "data/transcripts/spotify_zh")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    ids, episode_count = expected_ids(args.evidence_pack)
    duplicate_expected_ids = sorted(
        episode_id for episode_id in set(ids) if ids.count(episode_id) > 1
    )
    missing_identity_count = episode_count - len(ids)
    result = {
        "evidence_pack": str(args.evidence_pack),
        "episode_count": episode_count,
        "missing_identity_count": missing_identity_count,
        "duplicate_expected_ids": duplicate_expected_ids,
        "original": language_result(ids, args.english_dir, chinese=False),
        "chinese": language_result(ids, args.chinese_dir, chinese=True),
    }
    issues = []
    if missing_identity_count or duplicate_expected_ids:
        issues.append("evidence_identity")
    for language in ("original", "chinese"):
        item = result[language]
        if item["missing_ids"] or item["duplicate_ids"] or item["incomplete_ids"]:
            issues.append(language)
    result["clean"] = not issues
    result["issue_languages"] = issues
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_clean and issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
