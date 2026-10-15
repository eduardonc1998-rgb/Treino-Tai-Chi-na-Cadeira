#!/usr/bin/env python3
"""Serve the mirrored SPA with a route fallback and block remote tracking/API calls."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class SPAHandler(SimpleHTTPRequestHandler):
    server_version = "SoonBodyMirror/1.0"

    def __init__(self, *args, directory: str, **kwargs):
        self.site_dir = Path(directory).resolve()
        super().__init__(*args, directory=str(self.site_dir), **kwargs)

    def send_head(self):
        raw_path = unquote(urlsplit(self.path).path).lstrip("/")
        candidate = (self.site_dir / raw_path).resolve()
        try:
            candidate.relative_to(self.site_dir)
        except ValueError:
            self.send_error(403, "Forbidden")
            return None
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if candidate.is_file() and candidate.suffix:
            return super().send_head()
        fallback = self.site_dir / "index.html"
        if not fallback.is_file():
            self.send_error(404, "Mirror index.html not found")
            return None
        self.path = "/index.html"
        return super().send_head()

    def end_headers(self):
        # Local browsing must not leak quiz answers to the live backend or pixels.
        self.send_header("Content-Security-Policy",
                         "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' blob:; "
                         "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                         "font-src 'self' data:; connect-src 'self'; frame-src 'self'; "
                         "object-src 'none'; base-uri 'self'")
        self.send_header("X-Mirror-Source", "soonbody-static-recovery")
        super().end_headers()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site", help="mirror site directory")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    directory = str(Path(args.site).resolve())
    server = ThreadingHTTPServer((args.host, args.port),
                                 lambda *a, **kw: SPAHandler(*a, directory=directory, **kw))
    print(f"Serving mirror from {directory} at http://{args.host}:{args.port} (SPA fallback enabled)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
