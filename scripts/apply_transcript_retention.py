#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from backup_spotify_transcripts_to_drive import identity, title_key
from env_utils import load_project_env
from translate_spotify_transcripts_to_zh import _source_is_already_chinese


ROOT = Path(__file__).resolve().parents[1]


def calendar_cutoff(today: date, months: int = 6) -> date:
    index = today.year * 12 + today.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def backup_records(receipts: list[Path], now: datetime) -> dict[str, dict[str, dict]]:
    records: dict[str, dict[str, dict]] = {"english": {}, "chinese": {}}
    folder_keys = {"english": "SPOTIFY_TRANSCRIPT_DRIVE_FOLDER_ID",
                   "chinese": "SPOTIFY_TRANSCRIPT_ZH_DRIVE_FOLDER_ID"}
    for path in receipts:
        payload = json.loads(path.read_text(encoding="utf-8"))
        completed = datetime.fromisoformat(payload.get("completed_at") or "")
        if completed.tzinfo is None or not timedelta(0) <= now - completed <= timedelta(hours=1):
            raise ValueError(f"Backup receipt is not fresh: {path}")
        if payload.get("status") != "verified_available_archive_backup":
            raise ValueError(f"Backup is not verified: {path}")
        for language, key in folder_keys.items():
            section = payload.get(language)
            if not section:
                continue
            if section.get("status") != "verified" or not os.environ.get(key) or section.get("folder_id") != os.environ[key]:
                raise ValueError(f"Backup folder or verification mismatch: {path}")
            records[language].update({row["name"]: row for row in section["files"]})
    return records


def pending_references(runs_dir: Path, state_db: Path) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    with sqlite3.connect(f"file:{state_db}?mode=ro", uri=True) as connection:
        seen = {row[0] for row in connection.execute("select guid from processed_episodes")}
    ids, titles, paths = set(), set(), set()
    for pattern, field in (("*-manifest.json", "new_episodes"), ("*-evidence-pack.json", "episodes")):
        for path in runs_dir.glob(pattern):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for episode in payload.get(field, []):
                if not episode.get("guid") or episode["guid"] in seen:
                    continue
                meta = episode.get("transcript") or episode
                value = meta.get("spotify_episode_id") or meta.get("source_episode_id")
                if value:
                    ids.add(str(value))
                titles.add((str(episode.get("podcast_title") or "").casefold().strip(),
                            str(episode.get("episode_title") or "").casefold().strip()))
                if meta.get("path"):
                    paths.add(Path(meta["path"]).name)
    return ids, titles, paths


def chinese_preserves_original(original: dict, translated: dict, source_hash: str) -> bool:
    if translated.get("sourceTranscriptSha256") != source_hash:
        return False
    for key, value in original.items():
        if key not in {"segments", "debugLogs"} and translated.get(key) != value:
            return False
    source_segments, target_segments = original.get("segments", []), translated.get("segments", [])
    if len(source_segments) != len(target_segments):
        return False
    if not all(all(target.get(k) == v for k, v in source.items())
               for source, target in zip(source_segments, target_segments)):
        return False
    logs = original.get("debugLogs") or []
    return (translated.get("debugLogs") or [])[:len(logs)] == logs


def build_plan(transcript_dir: Path, cutoff: date, records: dict,
               protected: tuple[set[str], set[tuple[str, str]], set[str]]) -> list[dict]:
    ids, titles, protected_names = protected
    rows, chinese_by_id, chinese_by_title = [], {}, {}
    for language, directory in (("english", transcript_dir / "spotify_en"), ("chinese", transcript_dir / "spotify_zh")):
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink():
                continue
            raw = path.read_bytes()
            data = json.loads(raw)
            row = {"path": str(path), "name": path.name, "language": language,
                   "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                   "identity": identity(data), "title": title_key(data), "published": data.get("publishedDate"),
                   "is_chinese": language == "chinese" or _source_is_already_chinese(data["segments"]),
                   "complete": all(str(s.get("translation") or "").strip() for s in data["segments"] if str(s.get("text") or "").strip())}
            rows.append(row)
            if language == "chinese":
                if identity(data):
                    if identity(data) in chinese_by_id:
                        raise ValueError(f"Duplicate Chinese archive identity: {identity(data)}")
                    chinese_by_id[identity(data)] = row
                chinese_by_title[title_key(data)] = row
    for row in rows:
        reason = None
        try:
            published = date.fromisoformat(str(row["published"] or "")[:10])
        except ValueError:
            published = None
        if published is None:
            reason = "unknown_publication_date"
        elif published >= cutoff:
            reason = "within_retention_window"
        elif row["identity"] in ids or row["title"] in titles or row["name"] in protected_names:
            reason = "pending_report"
        backup_language, backup_name = row["language"], row["name"]
        if reason is None and row["language"] == "english":
            match = chinese_by_id.get(row["identity"]) if row["identity"] else chinese_by_title.get(row["title"])
            if match is None or not match["complete"]:
                reason = "pending_chinese_backfill"
            elif row["is_chinese"]:
                original = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
                translated = json.loads(Path(match["path"]).read_text(encoding="utf-8"))
                if not chinese_preserves_original(original, translated, row["sha256"]):
                    reason = "chinese_original_recovery_not_verified"
                else:
                    backup_language, backup_name = "chinese", match["name"]
                    row["backup_sha256"] = match["sha256"]
        if reason is None:
            record = records.get(backup_language, {}).get(backup_name)
            if not record or record.get("sha256") != row.get("backup_sha256", row["sha256"]):
                reason = "fresh_cloud_backup_not_verified"
        row["action"] = "keep" if reason else "delete"
        row["reason"] = reason or "expired_and_cloud_verified"
    return rows


def main() -> None:
    load_project_env()
    parser = argparse.ArgumentParser(description="Keep six calendar months locally; require fresh verified cloud backups before deletion.")
    parser.add_argument("--transcript-dir", type=Path, default=ROOT / "data/transcripts")
    parser.add_argument("--keep-months", type=int, choices=range(6, 121), default=6)
    parser.add_argument("--backup-receipt", type=Path, action="append", default=[])
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--plan-json", type=Path)
    args = parser.parse_args()
    if args.delete and not args.backup_receipt:
        raise SystemExit("Deletion requires fresh, verified English and Chinese cloud backup receipts")
    now = datetime.now(timezone.utc)
    records = backup_records(args.backup_receipt, now) if args.backup_receipt else {}
    if args.delete and (not records.get("english") or not records.get("chinese")):
        raise SystemExit("Deletion requires both language backup verifications")
    protected = pending_references(ROOT / "data/runs", ROOT / "data/state.sqlite")
    cutoff = calendar_cutoff(now.astimezone().date(), args.keep_months)
    rows = build_plan(args.transcript_dir, cutoff, records, protected)
    selected = [row for row in rows if row["action"] == "delete"]
    payload = {"created_at": now.isoformat(), "cutoff": cutoff.isoformat(), "mode": "delete" if args.delete else "preview",
               "eligible_files": len(selected), "eligible_bytes": sum(r["bytes"] for r in selected),
               "kept_files": len(rows) - len(selected), "files": rows, "deleted": []}
    plan_path = args.plan_json or ROOT / "data/service_logs" / f"{now.strftime('%Y%m%d-%H%M%S')}-transcript-retention.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.delete:
        # Validate the entire selection again before the first deletion.
        for row in selected:
            if hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() != row["sha256"]:
                raise SystemExit(f"File changed after planning; no cleanup started: {row['path']}")
        for row in selected:
            Path(row["path"]).unlink()
            payload["deleted"].append(row["path"])
            plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in {"files", "deleted"}}, ensure_ascii=False))
    print(plan_path)


if __name__ == "__main__":
    main()
