"""Post the daily blessing verse to the Truth of Bible social accounts.

Usage:
    python post_blessing.py            # dry run: prints the caption, renders the image, sends nothing
    python post_blessing.py --post     # publishes to every platform in PLATFORMS (default facebook,instagram)
    python post_blessing.py --post --facebook-only
    python post_blessing.py --check    # read-only check of the tokens and linked accounts
    python post_blessing.py --history  # recent posts and failures

A platform that already has a published post today is skipped, so re-running
after a partial failure only retries what failed and never double-posts.

Config is read from a .env file next to this script (see .env.example).
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

import designs
from tob_social import config, publishers
from tob_social.history import FAILED, PUBLISHED, History

HERE = Path(__file__).resolve().parent
HISTORY_DB = HERE / "data" / "history.db"
LEGACY_LOG = HERE / "post_log.txt"


def todays_verse(today):
    verses = json.loads((HERE / "verses.json").read_text(encoding="utf-8"))
    # Rotate by day of year so consecutive days never repeat a verse.
    return verses[today.timetuple().tm_yday % len(verses)]


def build_message(verse, env):
    lines = [
        "\U0001F64F Today's Blessing \U0001F64F",
        "",
        f"“{verse['text']}”",
        f"— {verse['ref']} (KJV)",
        "",
        "May the Lord bless you and keep you today. ❤️",
    ]
    if env.get("APP_LINK"):
        lines += ["", f"\U0001F4D6 Read more on the Truth of Bible app: {env['APP_LINK']}"]
    lines += ["", env.get("HASHTAGS", "#TruthOfBible #BibleVerse #DailyBlessing #GodBlessYou")]
    return "\n".join(lines)


def log(line, path=LEGACY_LOG):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {line}\n")


def publish_all(pubs, post, today, history, verse, style, log_path=LEGACY_LOG):
    """Publish to each platform not yet done today.
    Returns one {"platform", "status", "post_id", "error"} per platform; status is
    PUBLISHED, FAILED, or SKIPPED (already posted today)."""
    results = []
    for pub in pubs:
        done = history.published(pub.name, today)
        if done:
            print(f"{pub.name}: already posted today ({done['provider_post_id']}), skipping")
            post.image_url = post.image_url or done["asset_url"]
            results.append({"platform": pub.name, "status": "SKIPPED", "post_id": done["provider_post_id"], "error": None})
            continue
        try:
            result = pub.publish(post)
        except publishers.PublishError as e:
            history.record(pub.name, today, FAILED, verse_ref=verse["ref"], design=style,
                           caption=post.caption, error=str(e))
            print(f"{pub.name}: FAILED - {e}")
            results.append({"platform": pub.name, "status": FAILED, "post_id": None, "error": str(e)})
            continue
        post.image_url = post.image_url or result.image_url
        history.record(pub.name, today, PUBLISHED, verse_ref=verse["ref"], design=style, caption=post.caption,
                       provider_post_id=result.post_id, asset_url=result.image_url)
        log(f"{pub.name} {result.post_id} {verse['ref']}", log_path)
        print(f"{pub.name}: posted {result.post_id}")
        results.append({"platform": pub.name, "status": PUBLISHED, "post_id": result.post_id, "error": None})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post the daily blessing verse.")
    parser.add_argument("--post", action="store_true", help="publish (without this flag nothing is sent)")
    parser.add_argument("--facebook-only", action="store_true", help="post to Facebook only")
    parser.add_argument("--design", choices=designs.STYLES, help="image style (default: DESIGN in .env, else royal)")
    parser.add_argument("--check", action="store_true", help="read-only check of tokens and linked accounts")
    parser.add_argument("--history", action="store_true", help="show recent posts and failures")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji-safe under schedulers

    env = config.load_env(HERE / ".env")
    history = History(HISTORY_DB)
    history.import_legacy_log(LEGACY_LOG)
    names = ["facebook"] if args.facebook_only else config.platforms(env)

    if args.history:
        for row in history.recent():
            detail = row["provider_post_id"] or row["error"]
            print(f"{row['post_date']}  {row['platform']:<10} {row['status']:<9} {row['verse_ref'] or '':<22} {detail}")
        return 0

    if args.check or args.post:
        try:
            pubs = publishers.build(names, env)
        except ValueError as e:
            sys.exit(str(e))

    if args.check:
        for pub in pubs:
            try:
                print(f"{pub.name}: {pub.check()}")
            except publishers.PublishError as e:
                print(f"{pub.name}: FAILED - {e}")
        return 0

    today = config.local_today(env)
    verse = todays_verse(today)
    caption = build_message(verse, env)
    style = args.design or env.get("DESIGN", "royal")
    image = designs.render(verse, style, HERE / "today.png")
    print(caption)
    print(f"\nImage ({style}): {image}")
    print(f"Date: {today}")
    for name in names:
        done = history.published(name, today)
        print(f"  {name}: {'already posted today' if done else 'not posted yet'}")

    if not args.post:
        print("\n[dry run] Nothing posted. Use --post to publish.")
        return 0

    print()
    results = publish_all(pubs, publishers.Post(caption, image), today, history, verse, style)
    return 1 if any(r["status"] == FAILED for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
