# jedi-browser

Full-screen Termux web browser.

Purple matrix TUI, DuckDuckGo home, TLS 1.2+, cookies, gzip/brotli downloads, HTML5/JS chrome with images + CSS proxy.

https://github.com/jedisecX/jedi-browser

## Install

```bash
pkg install python ca-certificates git -y
pip install brotli   # optional, for Content-Encoding: br and .br saves
git clone https://github.com/jedisecX/jedi-browser.git
cd jedi-browser
python jedi-browser.py
```

Keep `jedi-browser.py`, `jb_core.py`, `jb_tui.py`, and `jb_web.py` together.

## Run

```bash
python jedi-browser.py
python jedi-browser.py --web
python jedi-browser.py --download https://example.com/file.pdf
python jedi-browser.py --download https://example.com/file.pdf --brotli
```

`--web` shows pictures and CSS (asset proxy + srcset/url() rewrite).

## Keys

`g` address  `b` back  `n` forward  `h` home  `d` gzip download  `D` brotli download  `r` reload  PgUp/PgDn scroll  `q` quit

## License

MIT
