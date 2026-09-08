import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from bankrag.evidence import can_publish, validate_answer


class EvidenceValidationTests(unittest.TestCase):
    def test_complete_official_chain_can_publish(self):
        answer = {
            "answer": "示例结论",
            "status": "supported",
            "claims": [{
                "claim": "示例事实",
                "evidence": [{
                    "document_id": "doc-1",
                    "chunk_id": "doc-1#p1",
                    "quote": "官方原文片段",
                    "source_url": "https://www.icbc.com.cn/page/1.html",
                    "retrieved_at": "2026-09-04T10:00:00+08:00",
                    "relation": "原文直接支持该事实"
                }]
            }]
        }
        self.assertEqual(validate_answer(answer), [])
        self.assertTrue(can_publish(answer))

    def test_non_official_source_is_rejected(self):
        answer = {
            "answer": "示例结论",
            "status": "supported",
            "claims": [{
                "claim": "示例事实",
                "evidence": [{
                    "document_id": "doc-1",
                    "chunk_id": "doc-1#p1",
                    "quote": "非官方内容",
                    "source_url": "https://example.com/a",
                    "retrieved_at": "2026-09-04T10:00:00+08:00"
                }]
            }]
        }
        self.assertFalse(can_publish(answer))
        self.assertTrue(any("not an approved" in error for error in validate_answer(answer)))


if __name__ == "__main__":
    unittest.main()
