"""Bounded official-page collection into a versioned SQLite evidence store."""
import argparse
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .ingest import make_snapshot

SEEDS = [
    ('个人结算账户', '721852549056724995'),
    ('整存整取', '721852502588030985'),
    ('个人通知存款', '721852427233165334'),
    ('挂失及密码重置', '721852503955374106'),
    ('个人客户星级服务', '721854339110174749'),
    ('业务协议', '721853401276383272'),
    ('转账汇款查询', '721852184605261838'),
]

def allowed(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'www.icbc.com.cn' and not p.username

class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Redirect outside collection allowlist')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.date = None
        self.in_title = False
        self.title_parts = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        if tag == 'meta' and a.get('name', '').lower() == 'icbcpostingdate':
            self.date = a.get('content')
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
    def handle_data(self, value):
        if self.in_title:
            self.title_parts.append(value.strip())

def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS documents(
      version_id TEXT PRIMARY KEY, url TEXT NOT NULL, title TEXT NOT NULL,
      published_at TEXT, retrieved_at TEXT NOT NULL, raw_hash TEXT NOT NULL,
      raw_path TEXT NOT NULL, text TEXT NOT NULL, review_status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chunks(
      chunk_id TEXT PRIMARY KEY, version_id TEXT REFERENCES documents(version_id),
      start_char INTEGER, end_char INTEGER, text TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS chunks_version ON chunks(version_id);
    CREATE TABLE IF NOT EXISTS fetch_log(
      url TEXT, fetched_at TEXT, status TEXT, detail TEXT);
    ''')
    return db

def store(db, root, url, title, raw):
    now = datetime.now(timezone.utc).isoformat()
    snap = make_snapshot('temporary', title, url, raw, now)
    # Keep repeated text: deleting repetitions can change contractual meaning.
    from .ingest import TextExtractor
    encoding = re.search(br'charset=["\x27]?([\w-]+)', raw[:4096], re.I)
    decoded = raw.decode(encoding.group(1).decode() if encoding else 'utf-8', errors='strict')
    parser = TextExtractor()
    parser.feed(decoded)
    text = '\n'.join(parser.parts)
    metadata = Links()
    metadata.feed(decoded)
    if '标题待核验' in title:
        title = ''.join(metadata.title_parts) or title
    if len(text) < 100 or '\ufffd' in text:
        raise ValueError('Empty or invalid extracted text')
    digest = hashlib.sha256(raw).hexdigest()
    version = hashlib.sha256((url + digest).encode()).hexdigest()
    raw_path = root / 'raw' / (digest + '.html')
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(raw)
    # All pages require currency/scope review before factual answer generation.
    with db:
        db.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?,?,?,?)',
            (version, url, title, metadata.date, now, digest, str(raw_path.resolve()), text, 'pending_review'))
        for start in range(0, len(text), 700):
            end = min(start + 900, len(text))
            db.execute('INSERT OR IGNORE INTO chunks VALUES(?,?,?,?,?)',
                (f'{version}:{start}:{end}', version, start, end, text[start:end]))
        db.execute('INSERT INTO fetch_log VALUES(?,?,?,?)', (url, now, 'ok', version))
    return metadata.links

def verify(db):
    count = 0
    data_dir = Path(db.execute('PRAGMA database_list').fetchone()[2]).resolve().parent
    for version, digest, path, text in db.execute('SELECT version_id,raw_hash,raw_path,text FROM documents'):
        assert hashlib.sha256((data_dir / 'raw' / (digest + '.html')).read_bytes()).hexdigest() == digest, path
        for start, end, fragment in db.execute('SELECT start_char,end_char,text FROM chunks WHERE version_id=?', (version,)):
            assert text[start:end] == fragment
            count += 1
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    return count

def refresh_titles(db):
    data_dir = Path(db.execute('PRAGMA database_list').fetchone()[2]).resolve().parent
    for version, digest in db.execute('SELECT version_id,raw_hash FROM documents').fetchall():
        parser = Links()
        parser.feed((data_dir / 'raw' / (digest + '.html')).read_text(encoding='utf-8'))
        title = ''.join(parser.title_parts)
        if title and title != '中国工商银行中国网站':
            db.execute('UPDATE documents SET title=? WHERE version_id=?', (title, version))
    db.commit()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=25)
    p.add_argument('--query')
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    root = Path('data')
    db = connect(root / 'icbc.sqlite3')
    if args.query:
        rows = db.execute('''SELECT d.title,d.url,d.published_at,d.retrieved_at,c.chunk_id,c.text,d.review_status
          FROM chunks c JOIN documents d USING(version_id) WHERE c.text LIKE ? LIMIT 5''', ('%' + args.query + '%',)).fetchall()
        print(json.dumps(rows, ensure_ascii=True, indent=2))
        return
    if args.verify:
        refresh_titles(db)
        print('Verified chunks:', verify(db))
        return
    queue = [(f'https://www.icbc.com.cn/page/{id}.html', title, 0) for title, id in SEEDS]
    seen = set()
    opener = build_opener(Redirects())
    successes = 0
    while queue and len(seen) < args.limit:
        url, title, depth = queue.pop(0)
        if url in seen or not allowed(url):
            continue
        seen.add(url)
        try:
            req = Request(quote(url, safe=':/%?=&'), headers={'User-Agent': 'BankRAGResearch/0.2'})
            with opener.open(req, timeout=20) as response:
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Not an HTML page; deferred')
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError('Page exceeds size limit')
            links = store(db, root, url, title, raw)
            successes += 1
            print('OK', successes, url, flush=True)
            if depth == 0:
                for href in links:
                    child = urljoin(url, href).split('#')[0]
                    if re.fullmatch(r'https://www.icbc.com.cn/page/\d+\.html', child) and child not in seen:
                        queue.append((child, '工商银行官方页面（标题待核验）', 1))
        except Exception as exc:
            with db:
                db.execute('INSERT INTO fetch_log VALUES(?,?,?,?)', (url, datetime.now(timezone.utc).isoformat(), 'error', str(exc)))
            print('ERROR', url, str(exc), flush=True)
        time.sleep(0.6)
    chunks = verify(db)
    report = {'collected_at': datetime.now(timezone.utc).isoformat(), 'attempted_this_run': len(seen),
      'successful_this_run': successes, 'document_versions': db.execute('SELECT count(*) FROM documents').fetchone()[0],
      'verified_chunks': chunks, 'review_status': 'pending_review', 'database': str((root / 'icbc.sqlite3').resolve())}
    (root / 'collection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))

if __name__ == '__main__':
    main()
