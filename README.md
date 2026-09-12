# jedi-browser

Full-screen Termux web browser in one Python script.

Purple matrix TUI with an address bar on top. DuckDuckGo as home. Verified TLS 1.2+. Persistent cookie jar. Optional HTML5/JS chrome that opens in Android WebView.

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

## Run

```bash
# full-screen TUI — address bar across the top
python jedi-browser.py

# start on a URL
python jedi-browser.py https://duckduckgo.com

# HTML5 + JavaScript chrome (real engine = Android browser / WebView)
python jedi-browser.py --web
```

`--web` serves `http://127.0.0.1:8765/` and launches `termux-open-url` when Termux:API is installed.

## Keys (TUI)

| Key | Action |
| --- | --- |
| `g` | focus address bar |
| Enter | go |
| `h` | home (DuckDuckGo) |
| `l` | toggle numbered links |
| `0`–`9` | follow link (in link mode) |
| `o` | open current URL in Android browser |
| `w` | hand off to w3m / lynx |
| `c` | show cookie jar |
| `r` | reload |
| `q` | quit |

Type a search (words with spaces) in the address bar to search DuckDuckGo.

## SSL / TLS

- HTTPS uses TLS 1.2 or newer
- Certificates are verified by default (`ca-certificates` on Termux, or `certifi` if installed)
- Status bar shows verify state / cipher when the stack exposes it
- `--insecure` skips verify — lab use only

```bash
pkg install ca-certificates
python jedi-browser.py --insecure   # do not use on the open web
```

## Cookies and login

Netscape cookie jar:

```
~/jedi/browse/cookies.txt
```

Shared by the TUI and the `--web` proxy. JS login forms need `--web` (the WebView runs the page). After you sign in there, the jar keeps the session for later TUI fetches.

Override the data directory with `JEDI_HOME`.

## What this is not

The TUI is a reader. It does not execute page JavaScript.

`--web` runs HTML5/JS in whatever opens the local chrome (Android browser / WebView). PHP is server-side: remote PHP sites work as HTML. Local `file:///.../*.php` is piped through `php` / `php-cgi` if installed.

For a full desktop engine on the phone: Termux:X11 + `pkg install x11-repo firefox`.

## Files written on device

| Path | What |
| --- | --- |
| `~/jedi/browse/cookies.txt` | cookie jar |
| `~/jedi/browse/history.jsonl` | visit log |
| `~/jedi/browse/downloads/` | non-HTML saves |

## License

MIT — see [LICENSE](LICENSE).
