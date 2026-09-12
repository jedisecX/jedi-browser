#!/usr/bin/env python3
"""HTML5/JS chrome + SSL proxy. Images and CSS rewritten through /proxy."""
from __future__ import annotations
import html as htmlmod
import os, re, socket, subprocess, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import jb_core
from jb_core import HOME_URL, WEB_PORT, download_url, fetch, normalize, save_cookies, which

CHROME_HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>Jedi Browser</title>
<style>
:root{--bg:#120018;--bar:#2a0040;--fg:#e2b8ff}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:15px ui-monospace,monospace}
#chrome{position:fixed;top:0;left:0;right:0;height:52px;display:flex;gap:6px;align-items:center;padding:6px 8px;background:var(--bar);z-index:10}
#chrome input{flex:1;height:38px;border:1px solid #6b2aa0;background:#1a0028;color:var(--fg);padding:0 10px}
#chrome button{height:38px;padding:0 8px;border:0;background:#4a148c;color:var(--fg);font-weight:700}
#chrome button:disabled{opacity:.35}
iframe{position:fixed;top:52px;left:0;right:0;bottom:0;width:100%;height:calc(100% - 52px);border:0;background:#fff;overflow:auto}
</style></head><body>
<form id=chrome><button type=button id=back>Back</button><button type=button id=fwd>Fwd</button>
<button type=button id=reload>Reload</button><button type=button id=home>Home</button>
<input id=addr value=HOME_URL><button type=submit>GO</button>
<button type=button id=dl>Save.gz</button><button type=button id=dlbr>Save.br</button>
<button type=button id=ext>Open</button></form>
<iframe id=view src=\"/proxy?url=HOME_ENC\"></iframe>
<script>
const HOME=\"HOME_URL\",addr=document.getElementById('addr'),view=document.getElementById('view');
const backBtn=document.getElementById('back'),fwdBtn=document.getElementById('fwd');
let stack=[HOME],idx=0;
function current(){return stack[idx]||HOME}
function sync(){addr.value=current();view.src='/proxy?url='+encodeURIComponent(current());backBtn.disabled=idx<=0;fwdBtn.disabled=idx>=stack.length-1}
function go(u){u=(u||addr.value||HOME).trim()||HOME;if(!/^[a-zA-Z][a-zA-Z0-9+.-]*:\\/\\//.test(u)&&u.indexOf(' ')<0)u='https://'+u;if(u.indexOf(' ')>=0&&u.indexOf('://')<0)u='https://duckduckgo.com/?q='+encodeURIComponent(u);stack=stack.slice(0,idx+1);if(stack[idx]!==u){stack.push(u);idx=stack.length-1}sync()}
document.getElementById('chrome').onsubmit=e=>{e.preventDefault();go(addr.value)};
document.getElementById('home').onclick=()=>go(HOME);
document.getElementById('reload').onclick=()=>{view.src=view.src};
document.getElementById('back').onclick=()=>{if(idx>0){idx--;sync()}};
document.getElementById('fwd').onclick=()=>{if(idx<stack.length-1){idx++;sync()}};
document.getElementById('dl').onclick=()=>{location.href='/dl?fmt=gzip&url='+encodeURIComponent(addr.value||HOME)};
document.getElementById('dlbr').onclick=()=>{location.href='/dl?fmt=br&url='+encodeURIComponent(addr.value||HOME)};
document.getElementById('ext').onclick=()=>{location.href='/open?url='+encodeURIComponent(addr.value||HOME)};
</script></body></html>"""

CSS_FIX = '<style id=jedi-css>img,picture,video,svg{max-width:100%!important;height:auto}</style>\n'

def proxied(page_url, val, root):
    val = (val or '').strip()
    if not val or val.startswith(('data:','javascript:','mailto:','tel:','#','blob:','about:')):
        return val
    absu = urllib.parse.urljoin(page_url, val)
    return root.rstrip('/') + '/proxy?url=' + urllib.parse.quote(absu, safe='')

def rewrite_srcset(page_url, value, root):
    out = []
    for chunk in value.split(','):
        chunk = chunk.strip()
        if not chunk: continue
        bits = chunk.split(); bits[0] = proxied(page_url, bits[0], root); out.append(' '.join(bits))
    return ', '.join(out)

def rewrite_css(page_url, css, root):
    def repl(m):
        q, val = m.group(1) or '', m.group(2)
        if val.startswith(('data:', '#')): return m.group(0)
        return f'url({q}{proxied(page_url, val, root)}{q})'
    css = re.sub(r"url\\(\\s*(['\"]?)([^')\"]+)\\1\\s*\\)", repl, css, flags=re.I)
    css = re.sub(r"@import\\s+(['\"])([^'\"]+)\\1", lambda m: f'@import {m.group(1)}{proxied(page_url, m.group(2), root)}{m.group(1)}', css, flags=re.I)
    return css

def rewrite_html(page_url, html_text, root):
    def prox_attr(m):
        attr, q, val = m.group(1), m.group(2), m.group(3)
        low = attr.lower()
        if low in {'srcset','imagesrcset'}: return f'{attr}={q}{rewrite_srcset(page_url, val, root)}{q}'
        if low == 'style': return f'{attr}={q}{rewrite_css(page_url, val, root)}{q}'
        if val.startswith(('data:','javascript:','mailto:','tel:','#','blob:')): return m.group(0)
        return f'{attr}={q}{proxied(page_url, val, root)}{q}'
    out = re.sub(r"\\b(href|src|action|poster|data-src|data-lazy-src|data-original|srcset|imagesrcset|style)\\s*=\\s*(['\"])(.*?)\\2", prox_attr, html_text, flags=re.I|re.S)
    out = re.sub(r'(<style\\b[^>]*>)(.*?)(</style>)', lambda m: m.group(1)+rewrite_css(page_url, m.group(2), root)+m.group(3), out, flags=re.I|re.S)
    if re.search(r'<head[^>]*>', out, re.I):
        out = re.sub(r'(<head[^>]*>)', r'\\1\\n'+CSS_FIX, out, count=1, flags=re.I)
    else:
        out = CSS_FIX + out
    return out.encode('utf-8', 'replace')

IMG_EXT = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.svg':'image/svg+xml','.ico':'image/x-icon','.avif':'image/avif','.bmp':'image/bmp'}

class BrowserHandler(BaseHTTPRequestHandler):
    proxy_root = f'http://127.0.0.1:{WEB_PORT}'
    def log_message(self, fmt, *args): sys.stderr.write('web '+(fmt%args)+'\n')
    def do_POST(self): self._handle(True)
    def do_GET(self): self._handle(False)
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(body)
    def _handle(self, post):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        body = b''
        if post:
            n = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(n) if n else b''
        if parsed.path in {'/','/index.html'}:
            page = CHROME_HTML.replace('HOME_URL', HOME_URL).replace('HOME_ENC', urllib.parse.quote(HOME_URL, safe=''))
            self._send(200, 'text/html; charset=utf-8', page.encode()); return
        if parsed.path == '/nav':
            url = normalize((qs.get('url') or [HOME_URL])[0])
            self.send_response(302); self.send_header('Location', '/proxy?url='+urllib.parse.quote(url, safe='')); self.end_headers(); return
        if parsed.path == '/open':
            self.send_response(302); self.send_header('Location', normalize((qs.get('url') or [HOME_URL])[0])); self.end_headers(); return
        if parsed.path == '/dl':
            url = normalize((qs.get('url') or [HOME_URL])[0])
            fmt = ((qs.get('fmt') or ['gzip'])[0] or 'gzip').lower()
            fmt = 'brotli' if fmt in {'br','brotli'} else ('none' if fmt in {'none','raw'} else 'gzip')
            try:
                info = download_url(url, compress=fmt!='none', method=fmt)
                data = info['path'].read_bytes()
                mime = 'application/x-brotli' if fmt=='brotli' else ('application/octet-stream' if fmt=='none' else 'application/gzip')
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Disposition', f'attachment; filename="{info["path"].name}"')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self._send(502, 'text/plain', f'download failed: {e}'.encode())
            return
        if parsed.path == '/proxy':
            url = normalize((qs.get('url') or [HOME_URL])[0])
            try:
                final, ctype, raw, text = fetch(url, data=body or None)
            except Exception as e:
                self._send(502, 'text/html; charset=utf-8', rewrite_html(url, f'<html><body><pre>{htmlmod.escape(str(e))}</pre></body></html>', self.proxy_root))
                return
            cl = ctype.lower()
            if 'html' in cl or text.lstrip()[:15].lower().startswith(('<!doctype','<html')):
                self._send(200, 'text/html; charset=utf-8', rewrite_html(final, text, self.proxy_root))
            elif 'css' in cl or final.lower().endswith('.css'):
                self._send(200, 'text/css; charset=utf-8', rewrite_css(final, text, self.proxy_root).encode('utf-8','replace'))
            else:
                mime = ctype.split(';')[0].strip() or 'application/octet-stream'
                ext = Path(urllib.parse.urlparse(final).path).suffix.lower()
                mime = IMG_EXT.get(ext, mime)
                self._send(200, mime, raw)
            return
        self._send(404, 'text/plain', b'not found')

def pick_port(preferred):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', preferred)); return preferred
        except OSError:
            s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def run_web(port):
    port = pick_port(port)
    BrowserHandler.proxy_root = f'http://127.0.0.1:{port}'
    httpd = ThreadingHTTPServer(('127.0.0.1', port), BrowserHandler)
    url = f'http://127.0.0.1:{port}/'
    print(f'Jedi HTML5 chrome  {url}')
    print(f'cookies {jb_core.COOKIE_FILE}')
    opened = False
    for b in ('termux-open-url','termux-open','xdg-open'):
        if which(b):
            subprocess.Popen([b, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            opened = True; break
    if not opened:
        print('open that URL on the phone')
    print('Ctrl+C to stop')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped'); save_cookies()
