# jedi-browser

Full-screen Termux web browser.

Purple matrix TUI with an address bar on top, history navigation, and a right-edge scrollbar. DuckDuckGo as home. Verified TLS 1.2+. Persistent cookie jar. Optional HTML5/JS chrome that opens in Android WebView.

**Public repo:** https://github.com/jedisecX/jedi-browser

## Install (Termux)

```bash
pkg update && pkg install python ca-certificates git -y
pkg install termux-api   # optional: termux-open-url
pkg install w3m lynx     # optional: hand off from TUI
pkg install php          # optional: local .php preview

git clone https://github.com/jedisecX/jedi-browser.git
cd jedi-browser
chmod +x jedi-browser.py
```

Keep `jedi-browser.py`, `jb_core.py`, `jb_tui.py`, and `jb_web.py` in the same folder.

## Run

```bash
python jedi-browser.py
python jedi-browser.py https://duckduckgo.com
python jedi-browser.py --web
```

## Navigation

TUI chrome (row under the address bar): `[<]back  [>]forward  [R]eload  [H]ome` plus a `#` thumb scrollbar on the right.

`--web` chrome: Back, Fwd, Reload, Home, address, GO, Open. Page area scrolls. Session history is kept in the toolbar JS.

## Keys (TUI)

| Key | Action |
| --- | --- |
| `g` | focus address bar |
| Enter | go |
| `b` | back |
| `n` | forward |
| `h` | home (DuckDuckGo) |
| PgUp / PgDn / arrows / space | scroll |
| `l` | toggle numbered links |
| `0`-`9` | follow link (in link mode) |
| `o` | open current URL in Android browser |
| `w` | hand off to w3m / lynx |
| `c` | show cookie jar |
| `r` | reload |
| `q` | quit |

## SSL / TLS

HTTPS uses TLS 1.2+ with certificate verify on by default. `--insecure` is lab-only.

## License

MIT — see [LICENSE](LICENSE).
