#!/usr/bin/env python3
"""Create index.html and rewrite mirrored first-party asset URLs to local paths."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

HOSTS = ("soonbody.com", "cdn.soonbody.com", "fonts.googleapis.com", "fonts.gstatic.com")
ASSET = re.compile(r"https?://(" + "|".join(re.escape(x) for x in HOSTS) + r")(/[^\"'`\s<>)]*?\.(?:js|css|woff2?|ttf|otf|png|jpe?g|webp|svg|gif|json|mp4|ico|avif)(?:\?[^\"'`\s<>)]*)?)", re.I)
FONTS_CSS2 = re.compile(r"https?://fonts\.googleapis\.com/css2\?[^\"'`\s<>)]*", re.I)
CF_SNIPPET = re.compile(r"<script>\s*\(function\(\)\{function c\(\).*?document\.addEventListener\('DOMContentLoaded'.*?\}\}\}\)\(\);</script>", re.S)
REMOTE_SCRIPT = re.compile(r"<script\b[^>]*\bsrc=[\"'](?:https?://(?!soonbody\.com/|cdn\.soonbody\.com/)[^\"']+|/metrics/[^\"']+)[\"'][^>]*>\s*</script>", re.I | re.S)
REMOTE_PRECONNECT = re.compile(r"<link\b(?=[^>]*\brel=[\"'](?:preconnect|dns-prefetch)[\"'])(?=[^>]*\bhref=[\"']https?://(?:us-assets\.i\.posthog\.com|load\.sgtm\.soonbody\.com|static\.cloudflareinsights\.com)[^\"']*[\"'])[^>]*>", re.I)
METRICS_SCRIPT = re.compile(r"<script\b(?=[^>]*\bsrc=[\"']/metrics/)[^>]*>\s*</script>", re.I | re.S)

def local_url(m: re.Match[str]) -> str:
    host, path = m.group(1).lower(), m.group(2)
    if host == "soonbody.com":
        return path
    return f"/_hosts/{host}{path}"

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site")
    ap.add_argument("--source", default="pt/flow-tai-chi-yoga-2")
    args = ap.parse_args()
    root = Path(args.site)
    source = root / args.source
    if not source.is_file():
        raise SystemExit(f"source HTML missing: {source}")
    for p in root.rglob("*"):
        if not p.is_file() or (p != source and p.suffix.lower() not in {".html", ".js", ".css", ".json", ".svg"}):
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        cooked = FONTS_CSS2.sub("/_hosts/fonts.googleapis.com/css2.css", raw)
        cooked = ASSET.sub(local_url, cooked)
        cooked = REMOTE_SCRIPT.sub("", cooked)
        cooked = REMOTE_PRECONNECT.sub("", cooked)
        cooked = METRICS_SCRIPT.sub("", cooked)
        cooked = re.sub(r"<script>window\.dataLayer=window\.dataLayer\|\|\[\];window\.dataLayer\.push\(\{\"fbPixelId\":.*?</script>", "", cooked, flags=re.S)
        if p.name == source.name and p.parent == source.parent:
            cooked = CF_SNIPPET.sub("", cooked)
        if cooked != raw:
            p.write_text(cooked, encoding="utf-8")
    (root / "index.html").write_bytes((root / args.source).read_bytes())
    print(f"Prepared {root / 'index.html'}; first-party static URLs now resolve locally.")

if __name__ == "__main__":
    main()
