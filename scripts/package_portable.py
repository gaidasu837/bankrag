"""Build and verify a portable archive from an explicit project allowlist."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from bankrag.import_graph import load_records

def main():
    load_records(ROOT / 'data/icbc.sqlite3')
    paths = [ROOT / n for n in ('README.md', 'MIGRATION.md', 'INSTALL_WINDOWS.md', 'QA_GUIDE.md', 'environment.yml', 'compose.yaml', '.gitignore')]
    pilot = ROOT / 'data/processed/pilot-20260908T065602050283Z'
    from bankrag.review_pilot import build
    build(pilot, ROOT / 'data/icbc.sqlite3')
    paths.extend(pilot / name for name in ('001.json', '002.json'))
    for folder in ('src', 'tests', 'config', 'schemas', 'scripts'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    archive = out / 'bankrag-portable.zip'
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        data = stage / 'data'
        data.mkdir()
        source = sqlite3.connect((ROOT / 'data/icbc.sqlite3').as_uri() + '?mode=ro', uri=True)
        target = sqlite3.connect(data / 'icbc.sqlite3')
        source.backup(target)
        target.execute("UPDATE documents SET raw_path='raw/' || raw_hash || '.html'")
        # Diagnostic logs contain machine-specific paths and are not evidence.
        target.execute('DELETE FROM fetch_log')
        target.commit()
        digests = [r[0] for r in target.execute('SELECT DISTINCT raw_hash FROM documents')]
        target.close()
        source.close()
        entries = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths}
        entries['data/icbc.sqlite3'] = (data / 'icbc.sqlite3').read_bytes()
        for digest in digests:
            entries['data/raw/' + digest + '.html'] = (ROOT / 'data/raw' / (digest + '.html')).read_bytes()
        entries['MANIFEST.json'] = json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in entries.items()}, indent=2).encode()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, content in entries.items():
                z.writestr(name, content)
        with zipfile.ZipFile(archive) as z:
            z.extractall(stage / 'restore')
        docs, chunks = load_records(stage / 'restore/data/icbc.sqlite3')
        print(f'Restored and verified: {len(docs)} documents, {len(chunks)} chunks')
        review = build(stage / 'restore/data/processed' / pilot.name, stage / 'restore/data/icbc.sqlite3')
        print('Restored reviewed assertions:', len(review['assertions']))
    print(archive)

if __name__ == '__main__':
    main()
