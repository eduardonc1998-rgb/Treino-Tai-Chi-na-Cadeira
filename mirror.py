#!/usr/bin/env python3
"""Recursively mirror first-party static assets referenced by an HTML app."""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen

ASSET_EXT = r"(?:js|css|woff2?|ttf|otf|png|jpe?g|webp|svg|gif|json|mp4|ico|avif)"
ABS_RE = re.compile(rf"https?://[^\"'` )<>\s]+?\.{ASSET_EXT}(?:\?[^\"'`() <>\s]*)?", re.I)
PATH_RE = re.compile(
    rf"[\"'`(]((?:\.\.?/)+[A-Za-z0-9_@./-]+?\.{ASSET_EXT}(?:\?[^\"'`() <>\s]*)?|/(?:[A-Za-z0-9_@.-]+/)*[A-Za-z0-9_@.-]+\.{ASSET_EXT}(?:\?[^\"'`() <>\s]*)?|(?:_app|assets|img|media|fonts|images|funnels)/[A-Za-z0-9_@./-]+?\.{ASSET_EXT}(?:\?[^\"'`() <>\s]*)?)[\"'`)]",
    re.I,
)


class RefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("src", "href", "poster"):
            val = a.get(key)
            if val and (key == "src" or tag in ("link", "source", "video", "img")):
                self.refs.append(val.strip())
        srcset = a.get("srcset")
        if srcset:
            self.refs.extend(x.strip().split()[0] for x in srcset.split(",") if x.strip())


def is_static_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return bool(re.search(rf"\.{ASSET_EXT}$", path) or
                (parsed.netloc.lower() == "fonts.googleapis.com" and path == "/css2"))


def local_rel(url: str, origin_host: str) -> Path:
    p = urlparse(url)
    rel = p.path.lstrip("/") or "index.html"
    if p.netloc.lower() == "fonts.googleapis.com" and p.path == "/css2":
        rel = "css2.css"
    if p.netloc and p.netloc.lower() != origin_host.lower():
        rel = Path("_hosts") / p.netloc.lower() / rel
    return Path(rel)


def extract_refs(text: str, current_url: str) -> list[str]:
    found = []
    if "<html" in text[:1000].lower() or "<!doctype" in text[:1000].lower():
        p = RefParser()
        try:
            p.feed(text)
            found.extend(p.refs)
        except Exception:
            pass
    found.extend(m.group(0) for m in ABS_RE.finditer(text))
    found.extend(m.group(1) for m in PATH_RE.finditer(text))
    out = []
    seen = set()
    for ref in found:
        ref = ref.strip().rstrip(".,;)")
        if not ref or ref.startswith(("data:", "blob:", "#")):
            continue
        url = urldefrag(urljoin(current_url, ref))[0]
        if is_static_url(url) and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url", help="starting funnel URL")
    ap.add_argument("--dest", default="site", help="directory for mirrored files")
    ap.add_argument("--include-host", action="append", default=["cdn.soonbody.com", "fonts.googleapis.com", "fonts.gstatic.com"], help="additional first-party static host (repeatable)")
    ap.add_argument("--delay", type=float, default=0.03, help="delay between requests")
    args = ap.parse_args()

    start = args.url
    origin = urlparse(start)
    hosts = {origin.netloc.lower(), *[h.lower() for h in args.include_host]}
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    queue = deque([start])
    queued = {start}
    fetched = set()
    failures: list[tuple[str, str]] = []
    session_headers = {"User-Agent": "Mozilla/5.0 (compatible; funnel-mirror/1.0)"}

    while queue:
        url = queue.popleft()
        p = urlparse(url)
        if p.netloc.lower() not in hosts:
            continue
        rel = local_rel(url, origin.netloc)
        target = dest / rel
        if target.exists() and target.stat().st_size > 0:
            # Existing files are deliberately skipped for repeatable incremental runs.
            fetched.add(url)
            if url == start or target.suffix.lower() in (".html", ".js", ".css", ".json", ".svg"):
                try:
                    body = target.read_text(encoding="utf-8", errors="replace")
                    for ref in extract_refs(body, url):
                        if ref not in queued:
                            queued.add(ref); queue.append(ref)
                except OSError:
                    pass
            continue
        try:
            req = Request(url, headers=session_headers)
            with urlopen(req, timeout=35) as response:
                body = response.read()
                ctype = response.headers.get_content_type()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            fetched.add(url)
            print(f"OK {response.status} {len(body):>9} {url} -> {rel.as_posix()}")
            if ctype in ("text/html", "application/javascript", "text/javascript", "text/css", "application/json", "image/svg+xml") or target.suffix.lower() in (".html", ".js", ".css", ".json", ".svg"):
                text = body.decode("utf-8", errors="replace")
                for ref in extract_refs(text, url):
                    if ref not in queued and urlparse(ref).netloc.lower() in hosts:
                        queued.add(ref); queue.append(ref)
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "code", None) or str(e)
            failures.append((url, str(reason)))
            print(f"FAIL {reason} {url}", file=sys.stderr)
        time.sleep(max(0, args.delay))

    print(f"\nDownloaded/skipped: {len(fetched)}; failed: {len(failures)}")
    if failures:
        (dest / "mirror_failures.txt").write_text("\n".join(f"{u}\t{e}" for u, e in failures), encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
