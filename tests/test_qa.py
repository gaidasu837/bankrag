import io
import json
import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from bankrag.qa_app import select, groups, handler_for

class QATests(unittest.TestCase):
    def test_invalid_model_reference_is_blocked(self):
        response = {'done': True, 'message': {'content': '{"ids":["fabricated"]}'}}
        with patch('bankrag.qa_app.build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(json.dumps(response).encode())
            with self.assertRaises(ValueError):
                select('question', [{'id':'E1','quote':'text','condition':'','notes':[]}], 'test')

    def test_split_relations_keep_all_assertion_ids(self):
        rows = [dict(version_id='v',start_char=0,end_char=1,assertion_id=str(i),subject='a',predicate='p',object=str(i),note='note') for i in range(3)]
        result = groups(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['assertion_ids']), 3)

    def test_page_and_cross_origin_block(self):
        class Fake:
            lock = threading.Lock()
            jobs = {}
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Fake(), 8501))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            opener = build_opener(ProxyHandler({}))
            with opener.open(url) as r:
                self.assertIn('银行知识问答', r.read().decode())
            with self.assertRaises(HTTPError) as error:
                opener.open(Request(url+'/api/ask',data=b'{}',headers={'Origin':'https://example.com'}))
            self.assertEqual(error.exception.code,403)
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    unittest.main()
