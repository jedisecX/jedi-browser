#!/usr/bin/env python3
"""
jedi-browser — Termux full-screen browser (SSL + cookies + purple TUI)

  python jedi-browser.py
  python jedi-browser.py --web
  python jedi-browser.py --insecure
"""

from __future__ import annotations

import argparse
import sys

from jb_core import HOME_URL, WEB_PORT, download_url, ensure, init_session, normalize
from jb_tui import run_tui
from jb_web import run_web


def main() -> None:
    ensure()
    ap = argparse.ArgumentParser(description="Termux full-screen SSL browser")
    ap.add_argument("url", nargs="?", default=HOME_URL)
    ap.add_argument("--web", action="store_true", help="HTML5+JS chrome")
    ap.add_argument("--port", type=int, default=WEB_PORT)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verify")
    ap.add_argument("--download", metavar="URL", help="download URL to ~/jedi/browse/downloads")
    ap.add_argument("--no-gzip", action="store_true", help="save download uncompressed")
    ap.add_argument("--brotli", action="store_true", help="save download as .br (needs pip install brotli)")
    args = ap.parse_args()
    init_session(insecure=args.insecure)
    if args.download:
        method = "none" if args.no_gzip else ("brotli" if args.brotli else "gzip")
        info = download_url(args.download, compress=method != "none", method=method)
        print(info["path"])
        print(f"raw {info['bytes_in']}  stored {info['bytes_out']}  codec={info.get('codec')}")
        return
    start = normalize(args.url)
    if args.web:
        run_web(args.port)
        return
    if not sys.stdin.isatty():
        print("need a TTY, or pass --web")
        sys.exit(1)
    run_tui(start)


if __name__ == "__main__":
    main()
