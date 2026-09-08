"""Validate the evidence store, then idempotently import its provenance graph."""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
import sqlite3


def load_records(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        documents = [dict(r) for r in db.execute('SELECT * FROM documents')]
        chunks = [dict(r) for r in db.execute('SELECT * FROM chunks')]
    finally:
        db.close()
    if not documents or not chunks:
        raise ValueError('Evidence database is empty')
    versions = {d['version_id']: d for d in documents}
    for doc in documents:
        raw_file = path.resolve().parent / 'raw' / (doc['raw_hash'] + '.html')
        if hashlib.sha256(raw_file.read_bytes()).hexdigest() != doc['raw_hash']:
            raise ValueError('Raw snapshot hash mismatch: ' + doc['version_id'])
        doc['raw_path'] = 'raw/' + raw_file.name
        if hashlib.sha256((doc['url'] + doc['raw_hash']).encode()).hexdigest() != doc['version_id']:
            raise ValueError('Document version ID mismatch')
        doc['text_hash'] = hashlib.sha256(doc['text'].encode()).hexdigest()
    for chunk in chunks:
        doc = versions.get(chunk['version_id'])
        start, end = chunk['start_char'], chunk['end_char']
        if doc is None or not (0 <= start < end <= len(doc['text'])):
            raise ValueError('Invalid chunk reference or offsets')
        if doc['text'][start:end] != chunk['text']:
            raise ValueError('Chunk does not match source text')
    return documents, chunks


def write_graph(tx, documents, chunks):
    tx.run('''UNWIND $rows AS row
      MERGE (s:BankRagSource {url: row.url})
      MERGE (d:BankRagDocument {version_id: row.version_id})
      SET d += row
      MERGE (s)-[:HAS_VERSION]->(d)''', rows=documents).consume()
    tx.run('''UNWIND $rows AS row
      MATCH (d:BankRagDocument {version_id: row.version_id})
      MERGE (c:BankRagChunk {chunk_id: row.chunk_id})
      SET c += row
      MERGE (d)-[:HAS_CHUNK]->(c)''', rows=chunks).consume()
    count = tx.run('''UNWIND $ids AS id
      MATCH (d:BankRagDocument)-[:HAS_CHUNK]->(c:BankRagChunk {chunk_id:id})
      RETURN count(DISTINCT c) AS n''', ids=[c['chunk_id'] for c in chunks]).single()['n']
    if count != len(chunks):
        raise ValueError('Imported chunk count mismatch; transaction rolled back')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sqlite', type=Path, default=Path('data/icbc.sqlite3'))
    parser.add_argument('--uri', default='bolt://localhost:17687')
    parser.add_argument('--database', default='neo4j')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    documents, chunks = load_records(args.sqlite)
    print(json.dumps({'validated_documents': len(documents), 'validated_chunks': len(chunks)}))
    if args.dry_run:
        print('Validation passed. No changes made to Neo4j.')
        return
    from neo4j import GraphDatabase
    password = getpass.getpass('Neo4j password: ')
    with GraphDatabase.driver(args.uri, auth=('neo4j', password)) as driver:
        driver.verify_connectivity()
        with driver.session(database=args.database) as session:
            for label, key in [('BankRagSource', 'url'), ('BankRagDocument', 'version_id'), ('BankRagChunk', 'chunk_id')]:
                session.run(f'CREATE CONSTRAINT {label}_unique IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE').consume()
            session.execute_write(write_graph, documents, chunks)
    print('Import committed. Source -> Document version -> Chunk evidence graph is ready.')
    print('Business facts remain pending review; this is not yet a complete GraphRAG index.')


if __name__ == '__main__':
    main()
