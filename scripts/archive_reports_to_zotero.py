#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import random
import shutil
import sqlite3
import string
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path.home() / "Zotero" / "zotero.sqlite"
DEFAULT_STORAGE = Path.home() / "Zotero" / "storage"
DEFAULT_COLLECTION = "1.Spotify情报汇总"
FIELD_TITLE = 1
FIELD_ABSTRACT = 2
FIELD_DATE = 6
FIELD_LANGUAGE = 7
FIELD_URL = 13
ITEM_TYPE_ATTACHMENT = 3
ITEM_TYPE_REPORT = 34
LINK_MODE_IMPORTED_FILE = 0


def _key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(8))


def _value_id(connection: sqlite3.Connection, value: str) -> int:
    connection.execute("insert or ignore into itemDataValues(value) values (?)", (value,))
    row = connection.execute("select valueID from itemDataValues where value = ?", (value,)).fetchone()
    if row is None:
        raise RuntimeError(f"Failed to create Zotero value: {value}")
    return int(row[0])


def _set_field(connection: sqlite3.Connection, item_id: int, field_id: int, value: str) -> None:
    value_id = _value_id(connection, value)
    connection.execute(
        "insert or replace into itemData(itemID, fieldID, valueID) values (?, ?, ?)",
        (item_id, field_id, value_id),
    )


def _tag_id(connection: sqlite3.Connection, tag: str) -> int:
    tag = tag if tag.startswith("/") else f"/{tag}"
    connection.execute("insert or ignore into tags(name) values (?)", (tag,))
    row = connection.execute("select tagID from tags where name = ?", (tag,)).fetchone()
    if row is None:
        raise RuntimeError(f"Failed to create Zotero tag: {tag}")
    return int(row[0])


def _new_item(connection: sqlite3.Connection, library_id: int, item_type_id: int) -> tuple[int, str]:
    for _ in range(20):
        key = _key()
        try:
            cursor = connection.execute(
                "insert into items(itemTypeID, libraryID, key, synced) values (?, ?, ?, 0)",
                (item_type_id, library_id, key),
            )
            return int(cursor.lastrowid), key
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Could not create unique Zotero item key.")


def _title_from_markdown(markdown_path: Path) -> str:
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return markdown_path.stem


def _run_date(run_id: str) -> str:
    try:
        return datetime.strptime(run_id.split("-")[0], "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return datetime.now().strftime("%Y-%m-%d")


def _existing_item_id(
    connection: sqlite3.Connection,
    title: str,
    collection_id: int,
    item_type_id: int | None = None,
) -> int | None:
    type_clause = "and i.itemTypeID = ?" if item_type_id is not None else ""
    params: tuple[object, ...] = (FIELD_TITLE, collection_id, title)
    if item_type_id is not None:
        params = (FIELD_TITLE, collection_id, title, item_type_id)
    row = connection.execute(
        f"""
        select i.itemID
        from items i
        join collectionItems ci on ci.itemID = i.itemID
        join itemData d on d.itemID = i.itemID and d.fieldID = ?
        join itemDataValues v on v.valueID = d.valueID
        where ci.collectionID = ? and v.value = ?
        {type_clause}
        limit 1
        """,
        params,
    ).fetchone()
    return int(row[0]) if row else None


def _delete_item_tree(connection: sqlite3.Connection, item_id: int) -> None:
    child_rows = connection.execute(
        "select itemID from itemAttachments where parentItemID = ?",
        (item_id,),
    ).fetchall()
    for (child_id,) in child_rows:
        _delete_item_tree(connection, int(child_id))
    connection.execute("delete from items where itemID = ?", (item_id,))


def remove_legacy_report_items(connection: sqlite3.Connection, collection_id: int, titles: Iterable[str]) -> list[str]:
    removed: list[str] = []
    for title in titles:
        while True:
            item_id = _existing_item_id(connection, title, collection_id, ITEM_TYPE_REPORT)
            if item_id is None:
                break
            _delete_item_tree(connection, item_id)
            removed.append(f"removed_legacy_report={item_id} title={title}")
    return removed


def remove_direct_attachment_titles(connection: sqlite3.Connection, collection_id: int, titles: Iterable[str]) -> list[str]:
    removed: list[str] = []
    for title in titles:
        while True:
            item_id = _existing_item_id(connection, title, collection_id, ITEM_TYPE_ATTACHMENT)
            if item_id is None:
                break
            _delete_item_tree(connection, item_id)
            removed.append(f"removed_direct_pdf={item_id} title={title}")
    return removed


def _delivery_stem(markdown_path: Path) -> str:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    package_dir = ROOT / "data" / "gemini_inputs" / run_id
    source_manifest = package_dir / "source-manifest-original.json"
    if source_manifest.exists():
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
        until = manifest.get("until")
        if until:
            try:
                published_dt = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
                short = published_dt.astimezone(timezone(timedelta(hours=8))).strftime("%y%m%d")
            except ValueError:
                short = str(until)[:10].replace("-", "")[2:]
            return f"{short}-Spotify播客情报研报"
    manifest_path = package_dir / "episode-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report_window = manifest.get("report_window") if isinstance(manifest.get("report_window"), dict) else {}
        until = report_window.get("until") if isinstance(report_window, dict) else None
        if until:
            try:
                published_dt = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
                short = published_dt.astimezone(timezone(timedelta(hours=8))).strftime("%y%m%d")
            except ValueError:
                short = str(until)[:10].replace("-", "")[2:]
            return f"{short}-Spotify播客情报研报"
        episodes = manifest.get("episodes") or []
        if episodes and episodes[0].get("published_at"):
            published_at = episodes[0]["published_at"]
            try:
                published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                short = published_dt.astimezone(timezone(timedelta(hours=8))).strftime("%y%m%d")
            except ValueError:
                short = published_at[:10].replace("-", "")[2:]
            return f"{short}-Spotify播客情报研报"
    short = datetime.strptime(run_id[:8], "%Y%m%d").strftime("%y%m%d")
    return f"{short}-Spotify播客情报研报"


def _old_delivery_stem(markdown_path: Path) -> str:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    short = datetime.strptime(run_id[:8], "%Y%m%d").strftime("%y%m%d")
    count = len(markdown_path.read_text(encoding="utf-8").split("#### 情报 ")) - 1
    suffix = "26集试跑" if count == 26 else f"{count}集周批次"
    return f"{short}-Spotify播客情报研报-{suffix}"


def archive_report(
    connection: sqlite3.Connection,
    storage_dir: Path,
    collection_id: int,
    library_id: int,
    markdown_path: Path,
    pdf_path: Path,
    tags: list[str],
) -> str:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    title = f"Spotify 播客情报研报 {run_id}"
    existing = _existing_item_id(connection, title, collection_id)
    if existing:
        return f"skipped_existing={existing} title={title}"

    item_id, _ = _new_item(connection, library_id, ITEM_TYPE_REPORT)
    _set_field(connection, item_id, FIELD_TITLE, title)
    _set_field(connection, item_id, FIELD_DATE, _run_date(run_id))
    _set_field(connection, item_id, FIELD_LANGUAGE, "zh-CN")
    _set_field(connection, item_id, FIELD_URL, str(markdown_path.resolve()))
    _set_field(connection, item_id, FIELD_ABSTRACT, f"Gemini report generated from Spotify transcripts; source run {run_id}.")
    connection.execute("insert or ignore into collectionItems(collectionID, itemID) values (?, ?)", (collection_id, item_id))
    for tag in tags:
        connection.execute("insert or ignore into itemTags(itemID, tagID, type) values (?, ?, 0)", (item_id, _tag_id(connection, tag)))

    attachment_id, attachment_key = _new_item(connection, library_id, ITEM_TYPE_ATTACHMENT)
    attachment_dir = storage_dir / attachment_key
    attachment_dir.mkdir(parents=True, exist_ok=False)
    target_pdf = attachment_dir / pdf_path.name
    shutil.copy2(pdf_path, target_pdf)
    pdf_bytes = target_pdf.read_bytes()
    connection.execute(
        """
        insert into itemAttachments(
            itemID, parentItemID, linkMode, contentType, path, syncState, storageModTime, storageHash
        ) values (?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            attachment_id,
            item_id,
            LINK_MODE_IMPORTED_FILE,
            "application/pdf",
            f"storage:{target_pdf.name}",
            int(target_pdf.stat().st_mtime * 1000),
            hashlib.md5(pdf_bytes).hexdigest(),
        ),
    )
    _set_field(connection, attachment_id, FIELD_TITLE, target_pdf.name)
    return f"archived item={item_id} attachment={attachment_id} title={title}"


def archive_pdf_direct(
    connection: sqlite3.Connection,
    storage_dir: Path,
    collection_id: int,
    library_id: int,
    pdf_path: Path,
    title: str,
    report_date: str,
    tags: list[str],
    replace_existing: bool,
) -> str:
    existing = _existing_item_id(connection, title, collection_id, ITEM_TYPE_ATTACHMENT)
    if existing and not replace_existing:
        return f"skipped_existing={existing} title={title}"
    while existing:
        _delete_item_tree(connection, existing)
        existing = _existing_item_id(connection, title, collection_id, ITEM_TYPE_ATTACHMENT)

    attachment_id, attachment_key = _new_item(connection, library_id, ITEM_TYPE_ATTACHMENT)
    attachment_dir = storage_dir / attachment_key
    attachment_dir.mkdir(parents=True, exist_ok=False)
    target_pdf = attachment_dir / pdf_path.name
    shutil.copy2(pdf_path, target_pdf)
    pdf_bytes = target_pdf.read_bytes()
    connection.execute(
        """
        insert into itemAttachments(
            itemID, parentItemID, linkMode, contentType, path, syncState, storageModTime, storageHash
        ) values (?, null, ?, ?, ?, 0, ?, ?)
        """,
        (
            attachment_id,
            LINK_MODE_IMPORTED_FILE,
            "application/pdf",
            f"storage:{target_pdf.name}",
            int(target_pdf.stat().st_mtime * 1000),
            hashlib.md5(pdf_bytes).hexdigest(),
        ),
    )
    _set_field(connection, attachment_id, FIELD_TITLE, title)
    _set_field(connection, attachment_id, FIELD_DATE, report_date)
    _set_field(connection, attachment_id, FIELD_LANGUAGE, "zh-CN")
    connection.execute("insert or ignore into collectionItems(collectionID, itemID) values (?, ?)", (collection_id, attachment_id))
    for tag in tags:
        connection.execute("insert or ignore into itemTags(itemID, tagID, type) values (?, ?, 0)", (attachment_id, _tag_id(connection, tag)))
    return f"archived_direct_pdf={attachment_id} title={title}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive generated podcast reports into local Zotero.")
    parser.add_argument("reports", nargs="+", type=Path, help="Markdown report paths.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--tag", action="append", default=None)
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--direct-pdf", action="store_true", help="Create top-level PDF attachment items directly in the collection.")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--remove-legacy-report-items", action="store_true")
    args = parser.parse_args()
    tags = [tag if tag.startswith("/") else f"/{tag}" for tag in (args.tag or ["/unread", "/2605"])]

    if args.backup:
        backup_path = args.db.with_suffix(f".sqlite.backup-{int(time.time())}")
        shutil.copy2(args.db, backup_path)
        print(f"backup={backup_path}")

    connection = sqlite3.connect(args.db)
    connection.execute("pragma foreign_keys = on")
    try:
        row = connection.execute(
            "select collectionID, libraryID from collections where collectionName = ?",
            (args.collection,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"Zotero collection not found: {args.collection}")
        collection_id, library_id = int(row[0]), int(row[1])
        if args.remove_legacy_report_items:
            legacy_titles = [
                f"Spotify 播客情报研报 {path.stem.replace('-gemini-report', '')}"
                for path in args.reports
            ]
            for message in remove_legacy_report_items(connection, collection_id, legacy_titles):
                print(message)
            if args.direct_pdf:
                legacy_direct_titles = [_old_delivery_stem(path) for path in args.reports]
                for message in remove_direct_attachment_titles(connection, collection_id, legacy_direct_titles):
                    print(message)
        for markdown_path in args.reports:
            if not markdown_path.exists():
                raise SystemExit(f"Missing Markdown report: {markdown_path}")
            run_id = markdown_path.stem.replace("-gemini-report", "")
            if args.direct_pdf:
                pdf_path = ROOT / "reports" / "pdf" / f"{_delivery_stem(markdown_path)}.pdf"
                title = pdf_path.stem
                report_date = _run_date(run_id)
                if not pdf_path.exists():
                    raise SystemExit(f"Missing PDF report: {pdf_path}")
                print(archive_pdf_direct(connection, args.storage_dir, collection_id, library_id, pdf_path, title, report_date, tags, args.replace_existing))
                continue
            pdf_path = ROOT / "reports" / "pdf" / f"{markdown_path.stem}.pdf"
            if not pdf_path.exists():
                raise SystemExit(f"Missing PDF report: {pdf_path}")
            print(archive_report(connection, args.storage_dir, collection_id, library_id, markdown_path, pdf_path, tags))
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
