"""Scheduled worker for the daily blessing post and scheduled content posts (app
features, salvation prayers, ...), controlled from the Frappe control panel
(TOB Blessing Automation Settings). Run by a systemd timer every
15 minutes on the outreach VPS; see deploy/README.md.

Usage:
    python blessing_worker.py                 # one scheduled run
    python blessing_worker.py --dry-run       # decide + render, send/post/log nothing
    python blessing_worker.py --status        # show what the control panel says
    python blessing_worker.py --test-slack    # post a test message to the preview channel
    python blessing_worker.py --import-verses # copy verses.json KJV text into empty panel verses (never approves)
    python blessing_worker.py --import-content  # add content.json drafts to the panel (never approves)
    python blessing_worker.py --test-post [blessing|app_feature|salvation_prayer]  # post one NOW (recorded as TEST)
"""
import argparse
import json
import sys
from pathlib import Path

from tob_social import config
from tob_social.automation import Run, choose_content, choose_verse, local_now
from tob_social.frappe_client import META_PREFIX, FrappeClient, FrappeError
from tob_social.history import History
from tob_social.slack import Slack, SlackError

HERE = Path(__file__).resolve().parent


def make_slack(cfg, env):
    if cfg.get("preview_channel") != "Slack":
        return None
    try:
        # Frappe holds the token; .env is only a fallback until the one-time move.
        return Slack(cfg.get("slack_bot_token") or env.get("SLACK_BOT_TOKEN"), cfg.get("slack_channel_id"))
    except SlackError as e:
        print(f"slack disabled: {e}")
        return None


def migrate_token(frappe, cfg, env):
    """One-time move of secrets still in .env into Frappe, their only home: the Meta Page token into TOB Meta
    Connection, the Slack bot token into TOB Blessing Automation Settings. Frappe accepts each only while it
    has none. Returns True if anything was moved."""
    moved = False
    meta = cfg.get("meta") or {}
    if meta.get("status") == "Not Configured" and env.get("FB_PAGE_ACCESS_TOKEN"):
        result = frappe.call("seed_from_worker", page_id=env.get("FB_PAGE_ID", ""),
                             access_token=env["FB_PAGE_ACCESS_TOKEN"], prefix=META_PREFIX)
        print(f"Moved the Meta token into Frappe (TOB Meta Connection): {result.get('status')}. "
              "Remove FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN from .env.")
        moved = True
    # Only a Frappe that knows the field sends the key at all, so an older one is never asked.
    if "slack_bot_token" in cfg and not cfg["slack_bot_token"] and env.get("SLACK_BOT_TOKEN"):
        if frappe.call("seed_worker_secrets", slack_bot_token=env["SLACK_BOT_TOKEN"]).get("moved"):
            print("Moved the Slack bot token into Frappe. Remove SLACK_BOT_TOKEN from .env.")
            moved = True
    return moved


def with_meta_token(cfg, env):
    """Use the Page token Frappe sends (TOB Meta Connection); .env no longer needs one."""
    meta = cfg.get("meta") or {}
    if meta.get("page_access_token"):
        return {**env, "FB_PAGE_ID": meta.get("page_id", ""), "FB_PAGE_ACCESS_TOKEN": meta["page_access_token"]}
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description="Daily blessing post worker.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="decide and render only; send, post and log nothing")
    group.add_argument("--status", action="store_true", help="show the control panel settings and approved verses")
    group.add_argument("--test-slack", action="store_true", help="send a test message to the preview channel")
    group.add_argument("--test-post", nargs="?", const="blessing", metavar="KIND",
                       help="post the next approved item now, ignoring time/switches/today's post (recorded as "
                            "TEST). KIND: blessing (default), app_feature, salvation_prayer, ...")
    group.add_argument("--import-verses", action="store_true", help="fill empty KJV text in the panel from verses.json")
    group.add_argument("--import-content", action="store_true", help="add content.json drafts to the panel")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    env = config.load_env(HERE / ".env")
    try:
        frappe = FrappeClient(env.get("FRAPPE_URL"), env.get("FRAPPE_API_KEY"), env.get("FRAPPE_API_SECRET"))
        if args.import_verses:
            verses = json.loads((HERE / "verses.json").read_text(encoding="utf-8"))
            result = frappe.import_verse_texts(verses)
            for key in ("filled", "created", "skipped", "unparsed"):
                print(f"{key}: {len(result[key])}  {', '.join(result[key])}")
            print("Nothing was approved. Check each text in the Desk and tick 'Checked & approved'.")
            return 0
        if args.import_content:
            items = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
            result = frappe.import_content(items)
            for key in ("created", "skipped"):
                print(f"{key}: {len(result[key])}  {', '.join(result[key])}")
            print("Nothing was approved. Check every item (app facts, prayers, Scripture) and tick "
                  "'Checked & approved'.")
            return 0
        cfg = frappe.config()
        if migrate_token(frappe, cfg, env):
            cfg = frappe.config()
    except FrappeError as e:
        # Without the control panel the worker never guesses: it posts nothing.
        print(f"ERROR: {e}")
        return 2
    env = with_meta_token(cfg, env)

    if args.status:
        pick = choose_verse(cfg["verses"])
        print(f"Automatic posting: {'ON' if cfg['enabled'] else 'OFF'}")
        print(f"Post time: {cfg['post_time']}  design: {cfg['design']}  platforms: {', '.join(cfg['platforms']) or '-'}")
        print(f"Preview: {cfg['preview_channel']} {cfg['slack_channel_id']} ({cfg['preview_minutes_before']} min before)")
        print(f"Approved verses: {len(cfg['verses'])}  next: {pick['reference'] if pick else '-'}")
        for sched in cfg.get("schedules") or []:
            days = ", ".join("Mon Tue Wed Thu Fri Sat Sun".split()[d] for d in sched.get("weekdays", [])) or "-"
            nxt = choose_content(sched.get("items", []))
            print(f"{sched['content_type']}: {'ON' if sched.get('enabled') else 'OFF'}  days: {days}  "
                  f"time: {sched.get('post_time')}  approved: {len(sched.get('items', []))}  "
                  f"next: {nxt['title'] if nxt else '-'}")
        return 0

    slack = make_slack(cfg, env)
    if args.test_slack:
        if not slack:
            print("Slack is not the preview channel, or its token/channel is missing.")
            return 1
        slack.post(":wave: Test from the Truth of Bible blessing worker — previews will appear here.")
        print("Sent.")
        return 0

    history = History(HERE / "data" / "history.db")
    history.import_legacy_log(HERE / "post_log.txt")
    now = local_now({"TIMEZONE": cfg.get("timezone") or env.get("TIMEZONE") or config.DEFAULT_TIMEZONE})
    run = Run(now, cfg, env, history, frappe, slack, out_image=HERE / "today.png", dry_run=args.dry_run)
    results = run.test_post(args.test_post) if args.test_post else run.execute()
    failed = isinstance(results, list) and any(r["status"] == "FAILED" for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
