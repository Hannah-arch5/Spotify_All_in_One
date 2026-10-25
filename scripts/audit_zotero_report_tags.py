#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess

from archive_reports_to_zotero import DEFAULT_COLLECTION, DEFAULT_DB, _tag_id

ROOT = Path(__file__).resolve().parents[1]
READING_TAGS = {'/read', '/reading'}


def report_tag_inventory(connection: sqlite3.Connection, collection: str) -> list[dict]:
    rows = connection.execute('''
        WITH RECURSIVE scope(collectionID) AS (
            SELECT collectionID FROM collections WHERE collectionName = ?
            UNION ALL
            SELECT c.collectionID FROM collections c JOIN scope s ON c.parentCollectionID = s.collectionID
        )
        SELECT DISTINCT i.itemID, i.key, v.value
        FROM scope s JOIN collectionItems ci USING(collectionID)
        JOIN items i USING(itemID)
        JOIN itemData d ON d.itemID=i.itemID AND d.fieldID=1
        JOIN itemDataValues v ON v.valueID=d.valueID
        WHERE i.itemTypeID IN (3,34)
          AND NOT EXISTS (SELECT 1 FROM deletedItems x WHERE x.itemID=i.itemID)
        ORDER BY i.itemID
    ''', (collection,)).fetchall()
    result = []
    for item_id, key, title in rows:
        tags = sorted(row[0] for row in connection.execute(
            'SELECT t.name FROM tags t JOIN itemTags it USING(tagID) WHERE it.itemID=?', (item_id,)))
        result.append({'item_id': item_id, 'key': key, 'title': title, 'tags': tags,
                       'missing_unread': '/unread' not in tags and not READING_TAGS.intersection(tags),
                       'preserved_reading_state': sorted(READING_TAGS.intersection(tags))})
    return result


def repair_missing_unread(connection: sqlite3.Connection, rows: list[dict]) -> list[int]:
    changed = []
    for row in rows:
        if not row['missing_unread']:
            continue
        connection.execute('INSERT OR IGNORE INTO itemTags(itemID,tagID,type) VALUES(?,?,0)',
                           (row['item_id'], _tag_id(connection, '/unread')))
        connection.execute("UPDATE items SET synced=0,dateModified=datetime('now'),clientDateModified=datetime('now') WHERE itemID=?",
                           (row['item_id'],))
        changed.append(row['item_id'])
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit Spotify report unread tags without resetting intentional read/reading states.')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--collection', default=DEFAULT_COLLECTION)
    parser.add_argument('--repair', action='store_true')
    parser.add_argument('--require-clean', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.repair:
        processes = subprocess.run(['pgrep', '-if', '/Zotero.app/Contents/MacOS/'], capture_output=True, text=True)
        if processes.returncode == 0:
            raise SystemExit('Zotero is running. Quit it normally before local database repair.')
        if processes.returncode != 1:
            raise SystemExit('Could not verify that Zotero is closed.')
    connection = sqlite3.connect(f'{args.db.resolve().as_uri()}?mode={"rw" if args.repair else "ro"}', uri=True)
    connection.execute('PRAGMA foreign_keys=ON')
    backup_path = None
    try:
        if args.repair:
            backup_path = ROOT / 'data/service_logs/zotero-backups' / f'zotero-before-unread-{datetime.now().strftime("%Y%m%d-%H%M%S")}.sqlite'
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(backup_path) as backup:
                connection.backup(backup)
            connection.execute('BEGIN IMMEDIATE')
        before = report_tag_inventory(connection, args.collection)
        if not before:
            raise SystemExit('No report items found in the specified collection.')
        changed = repair_missing_unread(connection, before) if args.repair else []
        after = report_tag_inventory(connection, args.collection)
        connection.commit()
    finally:
        connection.close()
    missing = [row for row in after if row['missing_unread']]
    payload = {'collection': args.collection, 'repair': args.repair, 'backup': str(backup_path) if backup_path else None,
               'total': len(after), 'changed_ids': changed, 'missing_before': [row for row in before if row['missing_unread']],
               'missing_after': missing, 'preserved_reading_states': [row for row in after if row['preserved_reading_state']]}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.require_clean and missing:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
