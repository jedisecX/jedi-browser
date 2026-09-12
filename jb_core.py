#!/usr/bin/env python3
"""Shared SSL session, cookies, fetch, HTML extract."""

from __future__ import annotations

import gzip
import html as htmlmod
import http.cookiejar
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from html.parser import HTMLParser
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
OPENER = None
JAR = None
SSL_CTX = None
LAST_TLS = ""

try:
    import brotli as _brotli
    HAS_BROTLI = True
except Exception:
    _brotli = None
    HAS_BROTLI = False

def accept_encoding():
    return "gzip, deflate, br" if HAS_BROTLI else "gzip, deflate"

def ensure():
    CACHE.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

def which(name):
    for p in os.environ.get("PATH", "").split(os.pathsep):
        c = Path(p) / name
        if c.is_file() and os.access(c, os.X_OK):
            return True
    return False

def build_ssl_context(insecure):
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
    candidates.extend([
        "/data/data/com.termux/files/usr/etc/tls/cert.pem",
        "/data/data/com.termux/files/usr/etc/ssl/certs/ca-certificates.crt",
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/ssl/cert.pem",
    ])
    for path in candidates:
        if path and Path(path).is_file():
            ctx.load_verify_locations(cafile=path)
            break
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx

def init_session(insecure=False):
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
        ("Accept-Encoding", accept_encoding()),
    ]

def brotli_decompress(raw):
    if not HAS_BROTLI or _brotli is None:
        return None
    try:
        return _brotli.decompress(raw)
    except Exception:
        return None

def brotli_compress(raw, quality=11):
    if not HAS_BROTLI or _brotli is None:
        raise RuntimeError("brotli not installed.  pip install brotli")
    return _brotli.compress(raw, quality=quality)

def decode_content(raw, encoding):
    enc = (encoding or "").lower()
    if not raw:
        return raw
    try:
        tokens = [p.strip() for p in enc.replace(";", ",").split(",") if p.strip()]
        if "br" in tokens:
            out = brotli_decompress(raw)
            if out is not None:
                return out
        if "gzip" in enc:
            return gzip.decompress(raw)
        if "deflate" in enc:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        return raw
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        try:
            return gzip.decompress(raw)
        except Exception:
            return raw
    br = brotli_decompress(raw)
    if br is not None and len(br) != len(raw):
        return br
    return raw

def unique_path(name):
    ensure()
    name = re.sub(r"[^\w.-]+", "_", name)[:80] or "download"
    path = DOWNLOADS / name
    n = 1
    while path.exists():
        path = DOWNLOADS / f"{n}_{name}"
        n += 1
    return path

def save_download(url, raw, compress=True, method="gzip"):
    ensure()
    base = Path(urllib.parse.urlparse(url).path).name or "download"
    orig = len(raw)
    method = (method or "gzip").lower()
    if not compress or method in {"none", "off", "raw"}:
        path = unique_path(base)
        path.write_bytes(raw)
        return {"path": path, "bytes_in": orig, "bytes_out": orig, "codec": "none", "gzip": False, "ratio": 1.0}
    if method in {"br", "brotli"}:
        path = unique_path(base if base.endswith(".br") else base + ".br")
        path.write_bytes(brotli_compress(raw))
        stored = path.stat().st_size
        return {"path": path, "bytes_in": orig, "bytes_out": stored, "codec": "brotli", "gzip": False, "ratio": (stored / orig) if orig else 0.0}
    if base.endswith(".gz"):
        path = unique_path(base)
        path.write_bytes(raw if (len(raw) >= 2 and raw[:2] == b"\x1f\x8b") else gzip.compress(raw, 9))
    else:
        path = unique_path(base + ".gz")
        with gzip.GzipFile(filename=base, mode="wb", fileobj=path.open("wb"), compresslevel=9) as zf:
            zf.write(raw)
    stored = path.stat().st_size
    return {"path": path, "bytes_in": orig, "bytes_out": stored, "codec": "gzip", "gzip": True, "ratio": (stored / orig) if orig else 0.0}

def download_url(url, compress=True, method="gzip"):
    final, ctype, raw, _text = fetch(normalize(url))
    info = save_download(final, raw, compress=compress, method=method)
    info["url"] = final
    info["ctype"] = ctype
    return info

def save_cookies():
    if JAR is None:
        return
    try:
        JAR.save(ignore_discard=True, ignore_expires=True)
    except Exception:
        pass

def normalize(raw):
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

def fetch(url, data=None):
    global LAST_TLS
    if OPENER is None:
        init_session(INSECURE)
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    with OPENER.open(req, timeout=TIMEOUT) as resp:
        final = resp.geturl()
        raw = decode_content(resp.read(), resp.headers.get("Content-Encoding", ""))
        ctype = resp.headers.get("Content-Type", "text/html")
        tls = ""
        try:
            sock = resp.fp.raw._sock
            if hasattr(sock, "version"):
                tls = f"{sock.version()} {sock.cipher()[0]}" if sock.cipher() else sock.version()
        except Exception:
            pass
        if tls:
            LAST_TLS = ("INSECURE " if INSECURE else "") + tls
        elif INSECURE:
            LAST_TLS = "TLS verify OFF"
        charset = "utf-8"
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            charset = m.group(1)
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        save_cookies()
        return final, ctype, raw, text

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip = 0
        self.parts = []
        self.links = []
        self.images = []
        self._in_a = False
        self._href = ""
        self._atext = []
    def handle_starttag(self, tag, attrs):
        ad = {k: (v or "") for k, v in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr", "blockquote"}:
            self.parts.append("\n")
        if tag == "img":
            src = (ad.get("src") or ad.get("data-src") or ad.get("data-lazy-src") or "").strip()
            if not src and ad.get("srcset"):
                src = ad.get("srcset", "").split(",")[0].split()[0]
            alt = (ad.get("alt") or "").strip()[:80]
            if src and not src.startswith("data:"):
                self.images.append((alt or "image", src))
                self.parts.append(f" [img:{alt or src[:40]}] ")
        if tag == "a":
            href = ad.get("href", "").strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:")):
                self._in_a = True
                self._href = href
                self._atext = []
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._in_a:
            label = re.sub(r"\s+", " ", "".join(self._atext)).strip()[:90]
            if self._href:
                self.links.append((label or self._href[:90], self._href))
            self._in_a = False
    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._in_a:
            self._atext.append(data)
        bit = re.sub(r"\s+", " ", data)
        if bit.strip():
            self.parts.append(bit)

def parse_html(base, text):
    p = Extractor()
    try:
        p.feed(text)
    except Exception:
        pass
    body = htmlmod.unescape("".join(p.parts))
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    links, seen = [], set()
    for label, href in p.links:
        absu = urllib.parse.urljoin(base, href)
        if absu in seen:
            continue
        seen.add(absu)
        links.append((label, absu))
    images, iseen = [], set()
    for alt, src in p.images:
        absu = urllib.parse.urljoin(base, src)
        if absu in iseen:
            continue
        iseen.add(absu)
        images.append((alt, absu))
    return {"title": p.title.strip() or base, "text": body, "links": links, "images": images}

def log_history(url, title):
    ensure()
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "url": url, "title": title}
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def cookie_count():
    return len(JAR) if JAR is not None else 0
