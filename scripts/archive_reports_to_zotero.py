#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import random
import shutil
import sqlite3
import string
import time
from pathlib import Path


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


def _existing_item_id(connection: sqlite3.Connection, title: str, collection_id: int) -> int | None:
    row = connection.execute(
        """
        select i.itemID
        from items i
        join collectionItems ci on ci.itemID = i.itemID
        join itemData d on d.itemID = i.itemID and d.fieldID = ?
        join itemDataValues v on v.valueID = d.valueID
        where ci.collectionID = ? and v.value = ?
        limit 1
        """,
        (FIELD_TITLE, collection_id, title),
    ).fetchone()
    return int(row[0]) if row else None


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive generated podcast reports into local Zotero.")
    parser.add_argument("reports", nargs="+", type=Path, help="Markdown report paths.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--tag", action="append", default=["unread", "2605"])
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

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
        for markdown_path in args.reports:
            pdf_path = ROOT / "reports" / "pdf" / f"{markdown_path.stem}.pdf"
            if not markdown_path.exists():
                raise SystemExit(f"Missing Markdown report: {markdown_path}")
            if not pdf_path.exists():
                raise SystemExit(f"Missing PDF report: {pdf_path}")
            print(archive_report(connection, args.storage_dir, collection_id, library_id, markdown_path, pdf_path, args.tag))
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
