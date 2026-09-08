"""Fetch allow-listed pages and preserve auditable source snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .evidence import OFFICIAL_DOMAINS


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(dict.fromkeys(self.parts))


def is_official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in OFFICIAL_DOMAINS or host.endswith(".icbc.com.cn")


def make_snapshot(source_id: str, title: str, url: str, html: bytes, retrieved_at: str) -> dict:
    if not is_official(url):
        raise ValueError(f"source is not on an approved official domain: {url}")
    digest = hashlib.sha256(html).hexdigest()
    decoder = re.search(br"charset=[\"']?([\w-]+)", html[:4096], re.I)
    encoding = decoder.group(1).decode("ascii", "ignore") if decoder else "utf-8"
    try:
        decoded = html.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        decoded = html.decode("utf-8", "replace")
    parser = TextExtractor()
    parser.feed(decoded)
    return {
        "document_id": source_id,
        "title": title,
        "source_url": url,
        "official_domain": urlparse(url).hostname,
        "published_at": None,
        "retrieved_at": retrieved_at,
        "content_hash": f"sha256:{digest}",
        "text": parser.text(),
    }


def fetch(source_id: str, title: str, url: str, output_dir: Path) -> Path:
    request = Request(url, headers={"User-Agent": "BankRAGResearch/0.1"})
    with urlopen(request, timeout=30) as response:
        html = response.read()
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    snapshot = make_snapshot(source_id, title, url, html, now)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{source_id}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="保存工行官方网页的可审计快照")
    parser.add_argument("source_id")
    parser.add_argument("title")
    parser.add_argument("url")
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    print(fetch(args.source_id, args.title, args.url, args.output))


if __name__ == "__main__":
    main()
