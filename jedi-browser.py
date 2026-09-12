#!/usr/bin/env python3
"""
jedi-browser — Termux full-screen browser (SSL + cookies + purple TUI)

  python jedi-browser.py              # full-screen purple TUI
  python jedi-browser.py --web        # HTML5/JS chrome (real engine)
  python jedi-browser.py --insecure   # skip TLS verify (don't)

Home: https://duckduckgo.com
Cookies: ~/jedi/browse/cookies.txt
TLS: verified by default (ca-certificates / certifi)
"""

from __future__ import annotations

import argparse
import curses
import html as htmlmod
import http.cookiejar
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME_URL = "https://duckduckgo.com"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Termux) AppleWebKit/537.36 "
    "(KHTML, like Gecko) JediBrowser/1.1 Chrome/120.0.0.0 Mobile Safari/537.36"
)
JEDI = Path(os.environ.get("JEDI_HOME", Path.home() / "jedi"))
CACHE = JEDI / "browse"
COOKIE_FILE = CACHE / "cookies.txt"
HISTORY_FILE = CACHE / "history.jsonl"
DOWNLOADS = CACHE / "downloads"
TIMEOUT = 30
WEB_PORT = 8765

INSECURE = False
OPENER: urllib.request.OpenerDirector | None = None
JAR: http.cookiejar.MozillaCookieJar | None = None
SSL_CTX: ssl.SSLContext | None = None
LAST_TLS = ""


def ensure() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)


def which(name: str) -> bool:
    for p in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(p) / name
        if c.is_file() and os.access(c, os.X_OK):
            return True
    return False


def build_ssl_context(insecure: bool) -> ssl.SSLContext:
    if insecure:
        ctx = ssl._create_unverified_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context()
    candidates = []
    try:
        import certifi
        candidates.append(certifi.where())
    except Exception:
        pass
    candidates.extend(
        [
            "/data/data/com.termux/files/usr/etc/tls/cert.pem",
            "/data/data/com.termux/files/usr/etc/ssl/certs/ca-certificates.crt",
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/ssl/cert.pem",
        ]
    )
    for path in candidates:
        if path and Path(path).is_file():
            ctx.load_verify_locations(cafile=path)
            break
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def init_session(insecure: bool = False) -> None:
    global OPENER, JAR, SSL_CTX, INSECURE, LAST_TLS
    INSECURE = insecure
    ensure()
    SSL_CTX = build_ssl_context(insecure)
    LAST_TLS = "TLS verify OFF" if insecure else "TLS verify ON"
    JAR = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    if COOKIE_FILE.exists() and COOKIE_FILE.stat().st_size > 0:
        try:
            JAR.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            JAR = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    https = urllib.request.HTTPSHandler(context=SSL_CTX)
    cookie = urllib.request.HTTPCookieProcessor(JAR)
    OPENER = urllib.request.build_opener(https, cookie)
    OPENER.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.9"),
        ("Accept-Encoding", "identity"),
    ]


def save_cookies() -> None:
    if JAR is None:
        return
    try:
        JAR.save(ignore_discard=True, ignore_expires=True)
    except Exception:
        pass


def normalize(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return HOME_URL
    low = raw.lower()
    if low in {"home", "ddg", "duckduckgo", "ducksuckgo.xom", "ducksuckgo.com"}:
        return HOME_URL
    if "://" not in raw and " " in raw:
        return "https://duckduckgo.com/?q=" + urllib.parse.quote_plus(raw)
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = "https://" + raw
    return raw
