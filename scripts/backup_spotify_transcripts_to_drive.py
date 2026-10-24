#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

from env_utils import load_project_env
from translate_spotify_transcripts_to_zh import _source_is_already_chinese


ROOT = Path(__file__).resolve().parents[1]


def identity(data: dict) -> str:
    return str(data.get("spotifyEpisodeId") or data.get("sourceEpisodeId") or "")


def title_key(data: dict) -> tuple[str, str]:
    return (str(data.get("podcastName") or "").casefold().strip(),
            str(data.get("episodeTitle") or "").casefold().strip())


def inventory(english_dir: Path, chinese_dir: Path, evidence_path: Path | None = None) -> dict:
    expected_paths = None
    if evidence_path:
        pack = json.loads(evidence_path.read_text(encoding="utf-8"))
        expected_paths = set()
        for episode in pack["episodes"]:
            meta = episode.get("transcript") or {}
            if not meta.get("path"):
                raise ValueError(f"Missing original transcript: {episode.get('index')}")
            path = Path(meta["path"])
            expected_paths.add((path if path.is_absolute() else ROOT / path).resolve())
    originals = []
    chinese = []
    incomplete = []
    for directory, rows, is_zh in ((english_dir, originals, False), (chinese_dir, chinese, True)):
        seen = set()
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            segments = data.get("segments")
            if not isinstance(segments, list) or not segments or not all(isinstance(s, dict) for s in segments):
                raise ValueError(f"Invalid transcript segments: {path}")
            key = ("id", identity(data)) if identity(data) else ("legacy-title", title_key(data))
            if key in seen:
                raise ValueError(f"Duplicate transcript identity in {directory}: {key}")
            seen.add(key)
            row = {"path": path, "identity": identity(data),
                   "data": {k: data.get(k) for k in ("podcastName", "episodeTitle")},
                   "is_chinese": _source_is_already_chinese(segments) if not is_zh else True}
            if is_zh and ("_zh_incomplete" in path.stem.casefold() or any(
                str(s.get("text") or "").strip() and not str(s.get("translation") or "").strip()
                for s in segments
            )):
                incomplete.append(str(path))
                continue
            rows.append(row)
    if expected_paths is not None:
        originals = [r for r in originals if r["path"].resolve() in expected_paths]
        if len(originals) != len(expected_paths):
            raise ValueError("Evidence pack references originals outside the archive")
    zh_by_id = {r["identity"]: r for r in chinese if r["identity"]}
    zh_legacy = {title_key(r["data"]): r for r in chinese if not r["identity"]}
    selected_zh = []
    missing = []
    for row in originals:
        match = zh_by_id.get(row["identity"]) if row["identity"] else None
        if match is None:
            match = zh_legacy.get(title_key(row["data"]))
        if match is None and not row["identity"]:
            match = next((r for r in chinese if title_key(r["data"]) == title_key(row["data"])), None)
        if match is None:
            missing.append(str(row["path"]))
        else:
            selected_zh.append(match)
    # Full-history backup includes complete legacy Chinese files, even without an original match.
    if expected_paths is None:
        selected_zh = chinese
    return {
        "english": [r["path"] for r in originals if not r["is_chinese"]],
        "chinese": list(dict.fromkeys(r["path"] for r in selected_zh)),
        "original_count": len(originals),
        "chinese_original_count": sum(r["is_chinese"] for r in originals),
        "missing_chinese_sources": missing,
        "incomplete_chinese_files": incomplete,
        "legacy_unidentified_originals": [str(r["path"]) for r in originals if not r["identity"]],
    }


def file_record(path: Path) -> dict:
    raw = path.read_bytes()
    return {"name": path.name, "size": len(raw), "md5": hashlib.md5(raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest()}


def verify_remote(records: list[dict], remote_rows: list[dict]) -> None:
    by_name = defaultdict(list)
    for row in remote_rows:
        if not row.get("IsDir"):
            by_name[row["Name"]].append(row)
    for record in records:
        matches = by_name[record["name"]]
        if len(matches) != 1:
            raise ValueError(f"Remote file missing or duplicated: {record['name']}")
        remote = matches[0]
        hashes = {k.lower(): v for k, v in remote.get("Hashes", {}).items()}
        if remote.get("Size") != record["size"] or hashes.get("md5") != record["md5"]:
            raise ValueError(f"Remote size/MD5 mismatch: {record['name']}")


def transfer(paths: list[Path], directory: Path, folder_id: str, remote: str,
             receipt_dir: Path, language: str, transfers: int = 4) -> dict:
    if not folder_id or not remote.endswith(":"):
        raise ValueError("Configure a pinned Drive folder ID and an rclone remote ending in ':'")
    records = [file_record(path) for path in paths]
    listing = receipt_dir / f"{language}-files.txt"
    listing.write_text("".join(path.name + "\n" for path in paths), encoding="utf-8")
    if any("\n" in path.name or "\r" in path.name for path in paths):
        raise ValueError("Transcript filenames must not contain newlines")
    flags = ["--drive-root-folder-id", folder_id, "--contimeout", "20s", "--timeout", "120s",
             "--retries", "3", "--low-level-retries", "5"]
    if paths:
        command = ["rclone", "copy", str(directory), remote, "--files-from-raw", str(listing),
                   "--checksum", "--transfers", str(transfers), "--checkers", "8",
                   "--stats", "30s", "--stats-log-level", "NOTICE", *flags]
        with (receipt_dir / f"{language}-transfer.log").open("a", encoding="utf-8") as log:
            subprocess.run(command, check=True, stdout=log, stderr=log, timeout=14400)
    result = subprocess.run(["rclone", "lsjson", remote, "--files-only", "--max-depth", "1",
                             "--hash", "--hash-type", "MD5", *flags], check=True,
                            capture_output=True, text=True, timeout=600)
    remote_rows = json.loads(result.stdout)
    (receipt_dir / f"{language}-remote.json").write_text(result.stdout, encoding="utf-8")
    verify_remote(records, remote_rows)
    for path, record in zip(paths, records):
        if file_record(path) != record:
            raise ValueError(f"Local file changed during backup: {path}")
    return {"status": "verified", "folder_id": folder_id, "file_count": len(paths),
            "bytes": sum(r["size"] for r in records), "files": records}


def main() -> None:
    load_project_env()
    parser = argparse.ArgumentParser(description="Incrementally back up verified subtitle archives without deleting remote files.")
    parser.add_argument("--english-dir", type=Path, default=ROOT / "data/transcripts/spotify_en")
    parser.add_argument("--chinese-dir", type=Path, default=ROOT / "data/transcripts/spotify_zh")
    parser.add_argument("--evidence-pack", type=Path)
    parser.add_argument("--language", choices=["all", "english", "chinese"], default="all")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--transfers", type=int, choices=range(1, 17), default=4)
    args = parser.parse_args()
    plan = inventory(args.english_dir, args.chinese_dir, args.evidence_pack)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    receipt_dir = args.receipt_dir or ROOT / "data/service_logs" / f"{stamp}-transcript-drive-backup"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"started_at": datetime.now().astimezone().isoformat(), "status": "planned", "language": args.language,
               "evidence_pack": str(args.evidence_pack) if args.evidence_pack else None,
               "plan": {k: [str(p) for p in v] if k in {"english", "chinese"} else v for k, v in plan.items()}}
    receipt_path = receipt_dir / "receipt.json"
    def save() -> None:
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    if args.plan_only:
        print(receipt_path)
        return
    if args.evidence_pack and args.language != "english" and plan["missing_chinese_sources"]:
        raise SystemExit("Current report Chinese transcripts are incomplete; backup cannot complete")
    try:
        for language, directory, env_key in [
            ("english", args.english_dir, "SPOTIFY_TRANSCRIPT_DRIVE_FOLDER_ID"),
            ("chinese", args.chinese_dir, "SPOTIFY_TRANSCRIPT_ZH_DRIVE_FOLDER_ID"),
        ]:
            if args.language not in {"all", language}:
                continue
            print(f"{language}: backing up {len(plan[language])} files", flush=True)
            receipt[language] = transfer(plan[language], directory, os.environ.get(env_key, ""),
                                         os.environ.get("SPOTIFY_TRANSCRIPT_DRIVE_REMOTE", "gdrive:"),
                                         receipt_dir, language, args.transfers)
            save()
            print(f"{language}: size and MD5 verified", flush=True)
        receipt["status"] = "verified_available_archive_backup"
        receipt["completed_at"] = datetime.now().astimezone().isoformat()
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = str(exc)
        raise
    finally:
        save()
    print(receipt_path)


if __name__ == "__main__":
    main()
