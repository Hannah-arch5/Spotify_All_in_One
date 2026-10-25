import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_zotero_report_tags import report_tag_inventory, repair_missing_unread
from archive_reports_to_zotero import archive_pdf_direct


class ZoteroUnreadTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            create table collections(collectionID integer primary key,collectionName text,parentCollectionID integer);
            create table collectionItems(collectionID integer,itemID integer);
            create table items(itemID integer primary key,key text,itemTypeID integer,synced integer,dateModified text,clientDateModified text);
            create table itemData(itemID integer,fieldID integer,valueID integer);
            create table itemDataValues(valueID integer primary key,value text);
            create table tags(tagID integer primary key,name text unique);
            create table itemTags(itemID integer,tagID integer,type integer,primary key(itemID,tagID));
            create table deletedItems(itemID integer);
            insert into collections values(1,'Spotify',null),(2,'Other',null);
            insert into tags values(1,'/read'),(2,'/reading'),(3,'/unread'),(4,'/urgent');
        ''')
        for i in range(1,7):
            self.db.execute('insert into items values(?,?,3,1,null,null)',(i,f'KEY{i}'))
            self.db.execute('insert into itemDataValues values(?,?)',(i,f'Report{i}'))
            self.db.execute('insert into itemData values(?,1,?)',(i,i))
            self.db.execute('insert into collectionItems values(?,?)',(2 if i==6 else 1,i))
        self.db.executescript('''insert into itemTags values(1,1,0),(2,2,0),(3,3,0),(4,4,0);insert into deletedItems values(5);''')

    def tearDown(self):
        self.db.close()

    def test_repair_preserves_read_states_other_tags_and_other_collections(self):
        rows = report_tag_inventory(self.db,'Spotify')
        self.assertEqual([4],repair_missing_unread(self.db,rows))
        after = report_tag_inventory(self.db,'Spotify')
        self.assertEqual([], [r for r in after if r['missing_unread']])
        self.assertEqual(['/read'],after[0]['tags'])
        self.assertEqual(['/reading'],after[1]['tags'])
        self.assertEqual(['/unread','/urgent'],after[3]['tags'])
        self.assertEqual([],repair_missing_unread(self.db,after))
        self.assertEqual(0,self.db.execute('select synced from items where itemID=4').fetchone()[0])
        self.assertEqual(0,self.db.execute('select count(*) from itemTags where itemID in(5,6)').fetchone()[0])

    def test_existing_archive_repairs_tags_without_replacing_pdf(self):
        result=archive_pdf_direct(self.db,Path('/nonexistent'),1,1,Path('/nonexistent.pdf'),'Report4','2026-10-05',['/unread','/2610'],False)
        self.assertIn('skipped_existing=4',result)
        tags=next(r['tags'] for r in report_tag_inventory(self.db,'Spotify') if r['item_id']==4)
        self.assertEqual(['/2610','/unread','/urgent'],tags)

    def test_existing_read_archive_does_not_reset_to_unread(self):
        archive_pdf_direct(self.db,Path('/nonexistent'),1,1,Path('/nonexistent.pdf'),'Report1','2026-10-05',['/unread','/2610'],False)
        tags=report_tag_inventory(self.db,'Spotify')[0]['tags']
        self.assertEqual(['/2610','/read'],tags)


if __name__ == '__main__':
    unittest.main()
