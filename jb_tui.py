#!/usr/bin/env python3
"""Purple matrix full-screen TUI."""
import curses, os, re, subprocess, urllib.error, urllib.parse
from pathlib import Path
import jb_core
from jb_core import DOWNLOADS, HOME_URL, COOKIE_FILE, JAR
from jb_core import cookie_count, fetch, log_history, normalize, parse_html, save_cookies, which

class TuiBrowser:
    def __init__(self, stdscr, start):
        self.stdscr = stdscr
        self.url = start
        self.title = ""
        self.lines = []
        self.links = []
        self.scroll = 0
        self.status = "home"
        self.mode = "view"
        self.edit = start
        self.edit_i = len(start)
        self.err = ""
        self.show_links = False
        curses.curs_set(0)
        try:
            curses.start_color(); curses.use_default_colors()
        except curses.error:
            pass
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
            curses.init_pair(3, curses.COLOR_MAGENTA, -1)
            curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)
        self.load(start)

    def load(self, url):
        url = normalize(url)
        self.url = self.edit = url
        self.edit_i = len(url)
        self.status = "loading..."
        self.err = ""
        self.draw()
        try:
            final, ctype, raw, text = fetch(url)
            if "html" not in ctype.lower() and not text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                path = self._save_download(final, raw)
                self.title = "download"
                self.lines = [f"saved {path}", f"{len(raw)} bytes", ctype]
                self.links = []
                self.url = final
                self.status = "download"
                return
            page = parse_html(final, text)
            self.url = self.edit = final
            self.edit_i = len(final)
            self.title = page["title"]
            self.links = page["links"][:200]
            wrap_w = max(20, curses.COLS - 2)
            self.lines = []
            for para in page["text"].splitlines() or [""]:
                self.lines.extend(self._wrap(para, wrap_w))
            if not self.lines:
                self.lines = ["(empty page)"]
            self.scroll = 0
            self.status = f"{len(self.links)} links · {cookie_count()} cookies"
            log_history(final, self.title)
        except urllib.error.URLError as e:
            self.err = str(getattr(e, "reason", e))
            self.lines = [f"SSL/load failed: {self.err}", "", "pkg install ca-certificates"]
            self.status = "tls/error"
        except Exception as e:
            self.err = str(e)
            self.lines = [f"load failed: {e}"]
            self.status = "error"

    def _save_download(self, url, raw):
        name = Path(urllib.parse.urlparse(url).path).name or "download"
        name = re.sub(r"[^\w.-]+", "_", name)[:80]
        path = DOWNLOADS / name
        n = 1
        while path.exists():
            path = DOWNLOADS / f"{n}_{name}"
            n += 1
        path.write_bytes(raw)
        return path

    def _wrap(self, para, width):
        para = para.strip()
        if not para:
            return [""]
        out, line = [], ""
        for word in para.split():
            if len(line) + len(word) + 1 <= width:
                line = (line + " " + word).strip()
            else:
                if line:
                    out.append(line)
                line = word
        if line:
            out.append(line)
        return out or [""]

    def draw(self):
        s = self.stdscr
        s.erase()
        h, w = s.getmaxyx()
        bar = self.edit if self.mode == "edit" else self.url
        if len(bar) > w - 8:
            bar = "..." + bar[-(w - 9):]
        try:
            s.addstr(0, 0, " ADDR ", curses.color_pair(2) | curses.A_BOLD)
            fill = (bar + " " * w)[: max(0, w - 6)]
            attr = curses.color_pair(5) | (curses.A_UNDERLINE if self.mode == "edit" else 0)
            s.addstr(0, 6, fill, attr)
            s.addstr(1, 0, (self.title or "")[: w - 1], curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass
        body_top, body_bot = 2, h - 2
        view_h = max(1, body_bot - body_top)
        if self.show_links:
            src = [f"{i:3d}  {lab[:max(10,w-28)]}  {urllib.parse.urlparse(href).netloc}"
                   for i, (lab, href) in enumerate(self.links, 1)] or ["(no links)"]
        else:
            src = self.lines
        self.scroll = max(0, min(self.scroll, max(0, len(src) - view_h)))
        for i in range(view_h):
            idx = self.scroll + i
            if idx >= len(src):
                break
            try:
                s.addstr(body_top + i, 0, src[idx][: w - 1], curses.color_pair(1))
            except curses.error:
                pass
        keys = "g addr  Enter  h home  l links  o android  c cookies  w w3m  q"
        foot = f"{self.status} · {jb_core.LAST_TLS} · {self.err[:24]} | {keys}"[: w - 1]
        try:
            s.addstr(h - 1, 0, foot + " " * max(0, w - 1 - len(foot)), curses.color_pair(2))
        except curses.error:
            pass
        if self.mode == "edit":
            curses.curs_set(1)
            try:
                s.move(0, min(6 + self.edit_i, w - 1))
            except curses.error:
                pass
        else:
            curses.curs_set(0)
        s.refresh()

    def run(self):
        while True:
            self.draw()
            ch = self.stdscr.get_wch()
            if self.mode == "edit":
                self._edit_key(ch)
                continue
            if ch in ("q", "Q"):
                save_cookies(); break
            if ch in ("g", "G", ":"):
                self.mode = "edit"; self.edit = self.url; self.edit_i = len(self.edit)
            elif ch in ("h", "H"):
                self.load(HOME_URL)
            elif ch in ("l", "L"):
                self.show_links = not self.show_links; self.scroll = 0
            elif ch in ("o", "O"):
                self._open_bin(self.url)
            elif ch in ("w", "W"):
                self._exec_first(self.url)
            elif ch in ("c", "C"):
                self._show_cookies()
            elif ch in ("r", "R"):
                self.load(self.url)
            elif ch == "KEY_NPAGE" or ch in (" ", "j"):
                self.scroll += max(1, curses.LINES - 5)
            elif ch == "KEY_PPAGE" or ch in ("k",):
                self.scroll -= max(1, curses.LINES - 5)
            elif ch == "KEY_DOWN":
                self.scroll += 1
            elif ch == "KEY_UP":
                self.scroll -= 1
            elif ch == "KEY_HOME":
                self.scroll = 0
            elif ch == "KEY_END":
                self.scroll = 10**9
            elif isinstance(ch, str) and ch.isdigit() and self.show_links:
                self._type_link_num(ch)

    def _show_cookies(self):
        rows = ["cookies -> " + str(COOKIE_FILE), ""]
        if JAR:
            for c in JAR:
                rows.append(f"{c.domain:24} {c.name}={c.value[:40]}")
        if len(rows) == 2:
            rows.append("(none yet - log in via --web for JS forms)")
        self.lines = rows
        self.show_links = False
        self.scroll = 0
        self.title = "cookie jar"
        self.status = f"{cookie_count()} cookies"

    def _type_link_num(self, first):
        buf = first
        self.status = f"link #{buf}_"
        self.draw()
        curses.timeout(800)
        while True:
            c = self.stdscr.get_wch()
            if c in ("KEY_ENTER", "\n", "\r"):
                break
            if isinstance(c, str) and c.isdigit():
                buf += c
                self.status = f"link #{buf}_"
                self.draw()
            else:
                break
        curses.timeout(-1)
        try:
            n = int(buf)
            if 1 <= n <= len(self.links):
                self.show_links = False
                self.load(self.links[n - 1][1])
        except ValueError:
            pass

    def _edit_key(self, ch):
        if ch in ("KEY_ENTER", "\n", "\r"):
            self.mode = "view"; self.load(self.edit); return
        if ch == "\x1b":
            self.mode = "view"; self.edit = self.url; return
        if ch in ("KEY_BACKSPACE", "\x7f", "\b"):
            if self.edit_i:
                self.edit = self.edit[:self.edit_i-1] + self.edit[self.edit_i:]
                self.edit_i -= 1
            return
        if ch == "KEY_LEFT":
            self.edit_i = max(0, self.edit_i - 1); return
        if ch == "KEY_RIGHT":
            self.edit_i = min(len(self.edit), self.edit_i + 1); return
        if ch == "KEY_HOME":
            self.edit_i = 0; return
        if ch == "KEY_END":
            self.edit_i = len(self.edit); return
        if isinstance(ch, str) and ch.isprintable():
            self.edit = self.edit[:self.edit_i] + ch + self.edit[self.edit_i:]
            self.edit_i += 1

    def _open_bin(self, url):
        for b in ("termux-open-url", "termux-open", "xdg-open"):
            if which(b):
                subprocess.Popen([b, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.status = f"opened {b}"; return
        self.status = "no opener"

    def _exec_first(self, url):
        save_cookies()
        for b in ("w3m", "lynx", "links"):
            if which(b):
                curses.endwin(); os.execvp(b, [b, url])
        self.status = "pkg install w3m"

def run_tui(start):
    def _main(stdscr):
        stdscr.keypad(True)
        TuiBrowser(stdscr, start).run()
    curses.wrapper(_main)
