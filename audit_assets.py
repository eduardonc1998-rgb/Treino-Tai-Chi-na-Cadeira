#!/usr/bin/env python3
"""Audit referenced static assets against a mirror; test source status for misses."""
from __future__ import annotations
import argparse
import re
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen

EXT = r"(?:js|css|woff2?|ttf|otf|png|jpe?g|webp|svg|gif|json|mp4|ico|avif)"
ABS = re.compile(rf"https?://[^\"'` )<>\s]+?\.{EXT}(?:\?[^\"'`() <>\s]*)?", re.I)
FONTS_CSS2 = re.compile(r"https?://fonts\.googleapis\.com/css2\?[^\"'`\s<>)]*", re.I)
PATH = re.compile(rf"[\"'`(]((?:\.\.?/)+[A-Za-z0-9_@./-]+?\.{EXT}(?:\?[^\"'`() <>\s]*)?|/(?:[A-Za-z0-9_@.-]+/)*[A-Za-z0-9_@.-]+\.{EXT}(?:\?[^\"'`() <>\s]*)?|(?:_app|assets|img|media|fonts|images|funnels)/[A-Za-z0-9_@./-]+?\.{EXT}(?:\?[^\"'`() <>\s]*)?)[\"'`)]", re.I)
ALLOWED = {"soonbody.com", "cdn.soonbody.com", "fonts.googleapis.com", "fonts.gstatic.com"}

def refs(text: str, base: str):
    values = list(ABS.findall(text)) + FONTS_CSS2.findall(text) + [m.group(1) for m in PATH.finditer(text)]
    seen = set()
    for value in values:
        u = urldefrag(urljoin(base, value.strip().rstrip(".,;")))[0]
        if u not in seen:
            seen.add(u)
            yield u

def mapped_path(url: str, root_host: str) -> Path | None:
    p = urlparse(url)
    if p.netloc.lower() not in ALLOWED:
        return None
    path = p.path.lstrip("/") or "index.html"
    if path.startswith("_hosts/"):
        return Path(path)
    if p.netloc.lower() == "fonts.googleapis.com" and p.path == "/css2":
        path = "css2.css"
    if p.netloc.lower() != root_host:
        path = f"_hosts/{p.netloc.lower()}/{path}"
    return Path(path)

def source_status(url: str) -> int | str:
    try:
        with urlopen(Request(url, method="HEAD", headers={"User-Agent":"funnel-asset-audit/1.0"}), timeout=15) as r:
            return r.status
    except HTTPError as e:
        if e.code not in (405, 501):
            return e.code
    except (URLError, TimeoutError, OSError) as e:
        return type(e).__name__
    try:
        req = Request(url, headers={"Range":"bytes=0-0", "User-Agent":"funnel-asset-audit/1.0"})
        with urlopen(req, timeout=15) as r:
            return r.status
    except HTTPError as e:
        return e.code
    except (URLError, TimeoutError, OSError) as e:
        return type(e).__name__

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site")
    ap.add_argument("--base-url", default="https://soonbody.com/")
    ap.add_argument("--check-remote", action="store_true", help="HEAD-test each missing first-party reference")
    args = ap.parse_args()
    root = Path(args.site).resolve()
    root_host = urlparse(args.base_url).netloc.lower()
    seen = set(); missing = []; external = defaultdict(int)
    text_ext = {".html", ".js", ".css", ".json", ".svg"}
    for file in root.rglob("*"):
        if not file.is_file() or file.suffix.lower() not in text_ext:
            continue
        rel = file.relative_to(root).as_posix()
        if rel.startswith("_hosts/"):
            _, host, *path = rel.split("/")
            base = f"https://{host}/" + "/".join(path)
        else:
            base = urljoin(args.base_url, rel)
        try:
            content = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for url in refs(content, base):
            if url in seen:
                continue
            seen.add(url)
            local = mapped_path(url, root_host)
            if local is None:
                external[urlparse(url).netloc.lower()] += 1
                continue
            if not (root / local).is_file():
                missing.append((url, local.as_posix()))
    statuses = []
    if args.check_remote:
        for url, local in missing:
            statuses.append((url, local, source_status(url)))
    present = len(seen) - len(missing) - sum(external.values())
    print(f"Static refs checked: {len(seen)}")
    print(f"Present locally: {present}")
    print(f"Missing locally: {len(missing)}")
    print("External hosts excluded: " + (", ".join(f"{h} ({n})" for h,n in sorted(external.items())) or "none"))
    if statuses:
        valid = [x for x in statuses if x[2] == 200]
        print("Missing references that exist on source (HTTP 200):")
        for u, p, status in valid: print(f"  {p} <- {u}")
        print("Missing references confirmed unavailable or non-200:")
        for u, p, status in statuses:
            if status != 200: print(f"  HTTP {status}: {u} [{p}]")
        (root.parent / "audit_remote_status.tsv").write_text("\n".join(f"{s}\t{u}\t{p}" for u,p,s in statuses), encoding="utf-8")
    else:
        for u, p in missing: print(f"  {p} <- {u}")
    return 1 if any(s == 200 for _,_,s in statuses) else (1 if missing and not args.check_remote else 0)

if __name__ == "__main__":
    raise SystemExit(main())
