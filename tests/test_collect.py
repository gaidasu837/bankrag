import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from bankrag.collect import connect, store, verify, allowed

class StoreTests(unittest.TestCase):
    def test_versions_and_exact_quotes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = connect(root / 'test.sqlite3')
            raw = ('<html><meta name="ICBCPostingDate" content="2024-01-01"><p>' + '重复条款。' * 250 + '</p></html>').encode()
            url = 'https://www.icbc.com.cn/page/1.html'
            store(db, root, url, 'test', raw)
            store(db, root, url, 'test', raw)
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0], 1)
            store(db, root, url, 'test', raw + b'changed')
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0], 2)
            self.assertGreater(verify(db), 0)
            path = Path(db.execute('SELECT raw_path FROM documents LIMIT 1').fetchone()[0])
            path.write_bytes(b'tampered')
            with self.assertRaises(AssertionError):
                verify(db)
            db.close()
    def test_allowlist(self):
        self.assertFalse(allowed('https://www.icbc.com.cn.evil.com/page/1.html'))
        self.assertFalse(allowed('http://www.icbc.com.cn/page/1.html'))
