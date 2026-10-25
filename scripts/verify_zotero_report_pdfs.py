#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path.home() / "Zotero" / "zotero.sqlite"
DEFAULT_STORAGE = Path.home() / "Zotero" / "storage"
FIELD_TITLE = 1
ITEM_TYPE_ATTACHMENT = 3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zotero_pdf_paths(db_path: Path, storage_dir: Path, title: str) -> list[Path]:
    # Immutable mode ignores WAL records, including freshly committed attachments.
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            select i.key, ia.path
            from items i
            join itemData d on d.itemID = i.itemID and d.fieldID = ?
            join itemDataValues v on v.valueID = d.valueID
            join itemAttachments ia on ia.itemID = i.itemID
            where i.itemTypeID = ? and v.value = ?
            """,
            (FIELD_TITLE, ITEM_TYPE_ATTACHMENT, title),
        ).fetchall()
    finally:
        connection.close()
    paths: list[Path] = []
    for key, storage_path in rows:
        filename = storage_path.replace("storage:", "", 1)
        paths.append(storage_dir / key / filename)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Zotero direct-PDF report items against local generated PDFs.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument('--require-tags', action='store_true', help='Require unread and the scheduled month tag on each current report.')
    parser.add_argument("pdfs", nargs="*", type=Path, default=[
        ROOT / "reports" / "pdf" / "260523-Spotify播客情报研报.pdf",
        ROOT / "reports" / "pdf" / "260525-Spotify播客情报研报.pdf",
    ])
    args = parser.parse_args()

    results = []
    for local_pdf in args.pdfs:
        local_pdf = local_pdf.resolve()
        local_hash = sha256(local_pdf) if local_pdf.exists() else None
        title = local_pdf.stem
        zotero_paths = zotero_pdf_paths(args.db, args.storage_dir, title)
        matches = []
        for zotero_path in zotero_paths:
            matches.append(
                {
                    "path": str(zotero_path),
                    "exists": zotero_path.exists(),
                    "sha256": sha256(zotero_path) if zotero_path.exists() else None,
                    "matches_local": zotero_path.exists() and local_hash == sha256(zotero_path),
                }
            )
        with sqlite3.connect(f'{args.db.resolve().as_uri()}?mode=ro', uri=True) as connection:
            tag_rows = connection.execute('''
                select i.itemID,t.name from items i
                join itemData d on d.itemID=i.itemID and d.fieldID=1
                join itemDataValues v on v.valueID=d.valueID
                left join itemTags it on it.itemID=i.itemID
                left join tags t on t.tagID=it.tagID
                where i.itemTypeID=3 and v.value=?
                  and not exists(select 1 from deletedItems x where x.itemID=i.itemID)
            ''', (title,)).fetchall()
        by_item = {}
        for item_id, tag in tag_rows:
            by_item.setdefault(item_id, set())
            if tag:
                by_item[item_id].add(tag)
        required_tags = {'/unread', f'/{title[:4]}'}
        tags_valid = bool(by_item) and all(required_tags.issubset(tags) for tags in by_item.values())
        results.append(
            {
                "title": title,
                "local_pdf": str(local_pdf),
                "local_exists": local_pdf.exists(),
                "local_sha256": local_hash,
                "zotero_matches": matches,
                "all_zotero_matches_local": bool(matches) and all(item["matches_local"] for item in matches),
                'required_tags': sorted(required_tags),
                'item_tags': {str(item_id): sorted(tags) for item_id,tags in by_item.items()},
                'all_zotero_tags_valid': tags_valid,
            }
        )
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    if args.require_tags and not all(row['all_zotero_matches_local'] and row['all_zotero_tags_valid'] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
