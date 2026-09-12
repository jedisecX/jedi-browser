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

from jb_core import HOME_URL, WEB_PORT, ensure, init_session, normalize
from jb_tui import run_tui
from jb_web import run_web


def main() -> None:
    ensure()
    ap = argparse.ArgumentParser(description="Termux full-screen SSL browser")
    ap.add_argument("url", nargs="?", default=HOME_URL)
    ap.add_argument("--web", action="store_true", help="HTML5+JS chrome")
    ap.add_argument("--port", type=int, default=WEB_PORT)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verify")
    args = ap.parse_args()
    init_session(insecure=args.insecure)
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
