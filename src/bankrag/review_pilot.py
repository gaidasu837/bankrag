"""Explicit review rules for the six pilot candidates; not a general reviewer."""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
from .import_graph import load_records

RULE_VERSION = 'pilot-review-v1'
RULES = {
    '部分提前支取的，提前支取的部分按支取日挂牌公告的活期存款利率计付利息，剩余部分到期时按开户日挂牌公告的定期储蓄存款利率计付利息。':
        ('整存整取定期存款', '支持', ['部分提前支取'], '部分提前支取时',
         '提前支取部分按支取日挂牌公告的活期存款利率计息；剩余部分到期按开户日挂牌公告的定期储蓄存款利率计息。'),
    '可质押贷款：如果定期存款临近到期，但又急需资金，客户可以办理质押贷款，以避免利息损失。':
        ('整存整取定期存款', '关联服务', ['质押贷款'], '原文描述情境：定期存款临近到期、客户急需资金',
         '原文未给出完整授信条件，不表示必然获批，也不表示仅该情境可申请。'),
    '客户可在存款时约定转存期限，定期存款到期后的本金和税后利息将自动按转存期限续存。':
        ('整存整取定期存款', '支持', ['约定转存'], '客户在存款时约定转存期限',
         '到期后的本金和税后利息自动按约定转存期限续存；税后利息为原文表述，不据此推断现行税制。'),
    '个人银行结算账户分为Ⅰ类银行账户、Ⅱ类银行账户和Ⅲ类银行账户（以下分别简称Ⅰ类户、Ⅱ类户和Ⅲ类户）。':
        ('个人银行结算账户', '分为', ['Ⅰ类银行账户', 'Ⅱ类银行账户', 'Ⅲ类银行账户'], '', '分类说明，不等于开户资格或数量限制。'),
    'Ⅰ类户是个人客户的全功能银行账户，广泛用于存款、购买投资理财产品等金融产品、转账、消费和缴费支付、支取现金等各类应用场景。':
        ('Ⅰ类银行账户', '可用于', ['存款', '购买投资理财产品等金融产品', '转账', '消费', '缴费支付', '支取现金'], '',
         '账户用途描述，不表示免于额度、适当性或具体办理条件要求。'),
}
EXCLUDED = '工商银行拥有丰富的个人结算产品，与多个行业建立了广泛的业务合作关系。'

def build(folder, db_path):
    docs, chunks = load_records(db_path)
    docs = {d['version_id']: d for d in docs}
    chunks = {c['chunk_id']: c for c in chunks}
    rows, excluded, seen = [], [], set()
    for name in ('001.json', '002.json'):
        raw = (folder / name).read_bytes()
        record = json.loads(raw)
        doc, chunk = docs[record['document_id']], chunks[record['chunk_id']]
        if chunk['version_id'] != doc['version_id'] or record.get('error'):
            raise ValueError('Invalid source record')
        for key, expected in [('source_url', doc['url']), ('raw_hash', doc['raw_hash'])]:
            if record.get(key) != expected:
                raise ValueError('Source metadata mismatch: ' + key)
        for fact in record['facts']:
            quote = fact['candidate']['quote']
            start, end = fact['start_char'], fact['end_char']
            if fact.get('rejection') is not None or not (chunk['start_char'] <= start < end <= chunk['end_char']):
                raise ValueError('Rejected candidate or invalid offsets')
            if doc['text'][start:end] != quote:
                raise ValueError('Quote mismatch')
            if quote in seen:
                raise ValueError('Duplicate pilot candidate')
            seen.add(quote)
            if quote == EXCLUDED:
                excluded.append({'quote': quote, 'reason': '营销性描述，不纳入业务关系'})
                continue
            if quote not in RULES:
                raise ValueError('Unreviewed quote: manual review required')
            subject, relation, objects, condition, note = RULES[quote]
            # Document identity supplies context not repeated inside every quote.
            expected_id = '721852502588030985' if subject == '整存整取定期存款' else '721852549056724995'
            if doc['url'] != f'https://www.icbc.com.cn/page/{expected_id}.html':
                raise ValueError('Unexpected product document')
            for obj in objects:
                row = dict(subject=subject, predicate=relation, object=obj, condition=condition, note=note,
                    quote=quote, start_char=start, end_char=end, chunk_id=chunk['chunk_id'], version_id=doc['version_id'],
                    source_url=doc['url'], raw_hash=doc['raw_hash'], published_at=doc['published_at'], retrieved_at=doc['retrieved_at'],
                    review_version=RULE_VERSION, semantic_status='explicit_rule_review', temporal_status='pending_review',
                    input_file=name, input_sha256=hashlib.sha256(raw).hexdigest())
                row['assertion_id'] = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                rows.append(row)
    if seen != set(RULES) | {EXCLUDED}:
        raise ValueError('Expected exactly the six reviewed pilot candidates')
    return {'review_version': RULE_VERSION, 'assertions': rows, 'excluded': excluded}

def write(tx, rows):
    # Check every source before any writes; failures roll back the transaction.
    for row in rows:
        result = tx.run('''MATCH (d:BankRagDocument {version_id:$v})-[:HAS_CHUNK]->(c:BankRagChunk {chunk_id:$c})
          RETURN d.raw_hash AS hash, d.text AS text, c.text AS chunk_text''', v=row['version_id'], c=row['chunk_id']).single()
        if not result or result['hash'] != row['raw_hash'] or result['text'][row['start_char']:row['end_char']] != row['quote'] or row['quote'] not in result['chunk_text']:
            raise ValueError('Neo4j evidence missing or inconsistent; import evidence graph first')
    tx.run('''UNWIND $rows AS row
      MATCH (c:BankRagChunk {chunk_id:row.chunk_id})
      MERGE (s:BankRagEntity {name:row.subject})
      MERGE (o:BankRagEntity {name:row.object})
      MERGE (a:BankRagAssertion {assertion_id:row.assertion_id}) SET a += row
      MERGE (a)-[:SUBJECT]->(s) MERGE (a)-[:OBJECT]->(o) MERGE (a)-[:SUPPORTED_BY]->(c)''', rows=rows).consume()
    count = tx.run('''MATCH (a:BankRagAssertion)-[:SUPPORTED_BY]->(:BankRagChunk)
      WHERE a.assertion_id IN $ids RETURN count(DISTINCT a) AS n''', ids=[r['assertion_id'] for r in rows]).single()['n']
    if count != len(rows):
        raise ValueError('Post-import count mismatch')
    return count

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--sqlite', type=Path, default=Path('data/icbc.sqlite3'))
    p.add_argument('--import-neo4j', action='store_true')
    p.add_argument('--uri', default='bolt://localhost:17687')
    args = p.parse_args()
    review = build(args.input, args.sqlite)
    output = args.input / 'reviewed-v1.json'
    content = json.dumps(review, ensure_ascii=False, indent=2)
    if output.exists() and output.read_text(encoding='utf-8') != content:
        raise ValueError('Existing review differs; preserve it and review changes before retrying')
    if not output.exists():
        output.write_text(content, encoding='utf-8')
    print(f'Validated assertions: {len(review["assertions"])}; excluded: {len(review["excluded"])}')
    print('Review: ' + str(output.resolve()))
    if args.import_neo4j:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(args.uri, auth=('neo4j', getpass.getpass('Neo4j password: '))) as driver:
            driver.verify_connectivity()
            with driver.session(database='neo4j') as session:
                for label, key in [('BankRagEntity', 'name'), ('BankRagAssertion', 'assertion_id')]:
                    session.run(f'CREATE CONSTRAINT {label}_unique IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE').consume()
                n = session.execute_write(write, review['assertions'])
                print(f'Imported and verified assertions: {n}')
    else:
        print('Preview only. Neo4j unchanged.')
    print('Temporal status: pending_review. No model calls performed.')

if __name__ == '__main__':
    main()
