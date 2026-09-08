import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from bankrag.ingest import make_snapshot


class IngestTests(unittest.TestCase):
    def test_snapshot_preserves_hash_and_visible_text(self):
        html = '<html><body><h1>个人账户</h1><script>secret()</script><p>办理说明</p></body></html>'.encode()
        item = make_snapshot(
            "account", "账户", "https://www.icbc.com.cn/account", html,
            "2026-09-04T10:00:00+08:00"
        )
        self.assertEqual(len(item["content_hash"]), 71)
        self.assertIn("个人账户", item["text"])
        self.assertNotIn("secret", item["text"])

    def test_rejects_unapproved_domain(self):
        with self.assertRaises(ValueError):
            make_snapshot("x", "x", "https://example.com", b"x", "2026-09-04T10:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
