# jedi-browser

Full-screen Termux web browser. Purple TUI, TLS 1.2+, cookies, HTML5/JS chrome, gzip downloads.

https://github.com/jedisecX/jedi-browser

## Install

```bash
pkg install python ca-certificates git -y
git clone https://github.com/jedisecX/jedi-browser.git
cd jedi-browser
python jedi-browser.py
```

## Downloads (gzip)

Saves: `~/jedi/browse/downloads/`

HTTP gzip/deflate is decoded for viewing. Saved files are gzip-compressed (level 9).

```bash
python jedi-browser.py --download https://example.com/file.pdf
python jedi-browser.py --download https://example.com/file.pdf --no-gzip
```

TUI: press `d`  |  `--web`: Save.gz button

## Keys

`g` address  `b` back  `n` forward  `h` home  `d` gzip download  `r` reload  PgUp/PgDn scroll  `q` quit

## License

MIT
