# Truth of Bible — Social Automation

Posts a daily blessing verse image to the Truth of Bible Facebook Page and Instagram.

The scheduled worker (`blessing_worker.py`) runs on the outreach VPS every 15 minutes and is
controlled from the Frappe app (`truthofbible-ai`): on/off, post time, design, platforms, Slack
preview channel, and the list of checked & approved verses. Every preview/post/failure is logged
to **TOB Automation Log** there. Deployment: [deploy/README.md](deploy/README.md).

## Setup
```
pip install -r requirements.txt
cp .env.example .env      # then fill in FB_PAGE_ACCESS_TOKEN
```

## Commands
| Command | What it does |
|---|---|
| `python post_blessing.py` | Dry run: prints the caption, renders `today.png`, sends nothing |
| `python post_blessing.py --post` | Publishes to every platform in `PLATFORMS` |
| `python post_blessing.py --post --facebook-only` | Facebook only |
| `python post_blessing.py --design modern_card` | Preview another style (dry run) |
| `python post_blessing.py --check` | Read-only check of the token and linked accounts |
| `python post_blessing.py --history` | Recent posts and failures |
| `python blessing_worker.py --status` | What the Frappe control panel currently says |
| `python blessing_worker.py --dry-run` | One scheduled run that sends, posts and logs nothing |
| `python designs.py` | Rebuild all style previews into `design_previews/` |
| `python -m unittest discover -s tests -t .` | Run the tests (no network access) |

## Safety
- One post per platform per day, enforced in `data/history.db`. Re-running after a
  partial failure only retries the platform that failed.
- `post_log.txt` is still written and is imported into the history database automatically.
- The scheduled worker only posts verses a person ticked as *Checked & approved* in Frappe;
  editing a verse's text clears its approval. Without the control panel it posts nothing.

## Layout
```
post_blessing.py          entry point (CLI)
designs.py                image styles (1080x1080)
verses.json               verse list ({ref, text}, KJV)
tob_social/config.py      .env loading, time zone, platform list
tob_social/history.py     SQLite post history + duplicate guard
tob_social/publishers/    one module per platform (base.py defines the interface)
tob_social/automation.py  one scheduled run: preview, post, log
tob_social/frappe_client.py, slack.py   control panel and preview channel clients
blessing_worker.py        scheduled entry point (systemd timer)
deploy/                   systemd units, setup script, deployment steps
tests/                    unit tests
```

## Adding a platform
Write a `Publisher` subclass in `tob_social/publishers/` (see `base.py`), add it to
`ORDER` and `build()` in `publishers/__init__.py`, then add its name to `PLATFORMS` in `.env`.
