#!/usr/bin/env python3
"""HTML5/JS chrome + SSL proxy with cookie jar."""
import html as htmlmod, os, re, socket, subprocess, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import jb_core
from jb_core import HOME_URL, COOKIE_FILE, WEB_PORT, fetch, normalize, save_cookies, which

CHROME_HTML = """<!DOCTYPE html><html lang=\"en\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Jedi Browser</title>
<style>
html,body{margin:0;height:100%;background:#120018;color:#e2b8ff;font:15px ui-monospace,monospace}
#chrome{position:fixed;top:0;left:0;right:0;height:52px;display:flex;gap:6px;align-items:center;padding:6px 8px;background:#2a0040;border-bottom:1px solid #5b1d8a;z-index:10}
#chrome input{flex:1;height:38px;border:1px solid #6b2aa0;background:#1a0028;color:#e2b8ff;padding:0 10px}
#chrome button{height:38px;padding:0 12px;border:0;background:#4a148c;color:#e2b8ff;font-weight:700}
iframe{position:fixed;top:52px;left:0;right:0;bottom:0;width:100%;height:calc(100% - 52px);border:0;background:#fff}
</style></head><body>
<form id=\"chrome\" action=\"/nav\" method=\"get\">
<button type=\"button\" id=\"home\">Home</button>
<input id=\"addr\" name=\"url\" value=\"HOME_URL\">
<button type=\"submit\">GO</button>
<button type=\"button\" id=\"ext\">Open</button>
</form>
<iframe id=\"view\" src=\"/proxy?url=HOME_ENC\" allow=\"fullscreen\"></iframe>
<script>
const HOME=\"HOME_URL\",addr=document.getElementById(\"addr\"),view=document.getElementById(\"view\");
function go(u){u=(u||addr.value||HOME).trim()||HOME;
if(!/^[a-zA-Z][a-zA-Z0-9+.-]*:\\/\\//.test(u)&&u.indexOf(\" \")===-1)u=\"https://\"+u;
if(u.indexOf(\" \")>=0&&u.indexOf(\"://\")===-1)u=\"https://duckduckgo.com/?q=\"+encodeURIComponent(u);
addr.value=u;view.src=\"/proxy?url=\"+encodeURIComponent(u);}
document.getElementById(\"chrome\").addEventListener(\"submit\",e=>{e.preventDefault();go(addr.value);});
document.getElementById(\"home\").onclick=()=>go(HOME);
document.getElementById(\"ext\").onclick=()=>{location.href=\"/open?url=\"+encodeURIComponent(addr.value||HOME);};
</script></body></html>
"""

TOOLBAR = (
    '<div id=\"jedi-bar\" style=\"position:sticky;top:0;z-index:2147483647;display:flex;gap:6px;'
    'align-items:center;padding:6px 8px;background:#2a0040;border-bottom:1px solid #5b1d8a;'
    'font:14px ui-monospace,monospace;\">'
    '<form method=\"get\" action=\"__NAV__\" style=\"display:flex;gap:6px;width:100%;margin:0;\">'
    '<button type=\"submit\" formaction=\"__HOME__\" style=\"height:34px;padding:0 10px;background:#4a148c;color:#e2b8ff;border:0;\">Home</button>'
    '<input name=\"url\" value=\"__URL__\" style=\"flex:1;height:34px;background:#1a0028;color:#e2b8ff;border:1px solid #6b2aa0;\">'
    '<button type=\"submit\" style=\"height:34px;padding:0 12px;background:#4a148c;color:#e2b8ff;border:0;\">GO</button>'
    '</form></div>'
)

def rewrite_html(page_url, html_text, proxy_root):
    base = f'<base href=\"{htmlmod.escape(page_url, quote=True)}\">\n'
    nav = proxy_root.rstrip('/') + '/nav'
    home = proxy_root.rstrip('/') + '/nav?url=' + urllib.parse.quote(HOME_URL, safe='')
    bar = (TOOLBAR.replace('__NAV__', htmlmod.escape(nav, quote=True))
           .replace('__HOME__', htmlmod.escape(home, quote=True))
           .replace('__URL__', htmlmod.escape(page_url, quote=True)))
    def prox(m):
        attr, q, val = m.group(1), m.group(2), m.group(3)
        if val.startswith(('data:', 'javascript:', 'mailto:', '#', 'blob:')):
            return m.group(0)
        absu = urllib.parse.urljoin(page_url, val)
        new = proxy_root.rstrip('/') + '/proxy?url=' + urllib.parse.quote(absu, safe='')
        return f'{attr}={q}{new}{q}'
    out = re.sub(r'''\b(href|src|action)\s*=\s*(['\"])([^'\"]+)\2''', prox, html_text, flags=re.I)
    if re.search(r'<head[^>]*>', out, re.I):
        out = re.sub(r'(<head[^>]*>)', r'\1\n' + base, out, count=1, flags=re.I)
    else:
        out = base + out
    if re.search(r'<body[^>]*>', out, re.I):
        out = re.sub(r'(<body[^>]*>)', r'\1\n' + bar, out, count=1, flags=re.I)
    else:
        out = bar + out
    return out.encode('utf-8', errors='replace')

def try_local_php(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'file':
        return None
    path = Path(urllib.parse.unquote(parsed.path))
    if not path.exists():
        return None
    if path.suffix.lower() != '.php':
        data = path.read_bytes()
        ctype = 'text/html; charset=utf-8' if path.suffix.lower() in {'.html', '.htm'} else 'application/octet-stream'
        return ctype, data
    php = 'php-cgi' if which('php-cgi') else ('php' if which('php') else None)
    if not php:
        return 'text/plain; charset=utf-8', b'php not installed. pkg install php'
    env = os.environ.copy()
    env.update({'REDIRECT_STATUS': '200', 'SCRIPT_FILENAME': str(path), 'REQUEST_METHOD': 'GET', 'QUERY_STRING': parsed.query})
    try:
        proc = subprocess.run([php, str(path)], capture_output=True, env=env, timeout=20)
        raw = proc.stdout
        if php.endswith('cgi') and (b'\r\n\r\n' in raw or b'\n\n' in raw):
            raw = raw.split(b'\r\n\r\n', 1)[-1] if b'\r\n\r\n' in raw else raw.split(b'\n\n', 1)[-1]
        return 'text/html; charset=utf-8', raw or proc.stderr
    except Exception as e:
        return 'text/plain; charset=utf-8', str(e).encode()

class BrowserHandler(BaseHTTPRequestHandler):
    proxy_root = f'http://127.0.0.1:{WEB_PORT}'
    def log_message(self, fmt, *args):
        sys.stderr.write('web ' + (fmt % args) + '\n')
    def do_POST(self):
        self._handle(True)
    def do_GET(self):
        self._handle(False)
    def _handle(self, post):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        body = b''
        if post:
            n = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(n) if n else b''
        if parsed.path in {'/', '/index.html'}:
            page = CHROME_HTML.replace('HOME_URL', HOME_URL).replace('HOME_ENC', urllib.parse.quote(HOME_URL, safe=''))
            self._send(200, 'text/html; charset=utf-8', page.encode())
            return
        if parsed.path == '/nav':
            url = normalize((qs.get('url') or [HOME_URL])[0])
            self.send_response(302)
            self.send_header('Location', '/proxy?url=' + urllib.parse.quote(url, safe=''))
            self.end_headers()
            return
        if parsed.path == '/open':
            self.send_response(302)
            self.send_header('Location', normalize((qs.get('url') or [HOME_URL])[0]))
            self.end_headers()
            return
        if parsed.path == '/proxy':
            url = normalize((qs.get('url') or [HOME_URL])[0])
            local = try_local_php(url)
            if local:
                ctype, data = local
                if 'html' in ctype:
                    data = rewrite_html(url, data.decode('utf-8', 'replace'), self.proxy_root)
                    ctype = 'text/html; charset=utf-8'
                self._send(200, ctype, data)
                return
            try:
                final, ctype, raw, text = fetch(url, data=body or None)
            except Exception as e:
                msg = f'<pre>SSL/fetch failed: {htmlmod.escape(str(e))}</pre>'
                self._send(502, 'text/html; charset=utf-8', rewrite_html(url, f'<html><body>{msg}</body></html>', self.proxy_root))
                return
            if 'html' in ctype.lower() or text.lstrip()[:15].lower().startswith(('<!doctype', '<html')):
                self._send(200, 'text/html; charset=utf-8', rewrite_html(final, text, self.proxy_root))
            else:
                self._send(200, ctype.split(';')[0], raw)
            return
        self._send(404, 'text/plain', b'not found')
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

def pick_port(preferred):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', preferred))
            return preferred
        except OSError:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

def run_web(port):
    port = pick_port(port)
    BrowserHandler.proxy_root = f'http://127.0.0.1:{port}'
    httpd = ThreadingHTTPServer(('127.0.0.1', port), BrowserHandler)
    url = f'http://127.0.0.1:{port}/'
    print(f'Jedi HTML5 chrome  {url}')
    print(f'Home               {HOME_URL}')
    print(f'Cookies            {COOKIE_FILE}')
    print(f"TLS                {'INSECURE' if jb_core.INSECURE else 'verified (TLS 1.2+)'}")
    if which('termux-open-url'):
        threading.Timer(0.4, lambda: subprocess.Popen(['termux-open-url', url])).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        save_cookies()
        print('\nbye')
