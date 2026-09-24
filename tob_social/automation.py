"""One run of the scheduled blessing automation (the systemd timer calls this
every 15 minutes). Every decision comes from the Frappe control panel, read
fresh on each run: on/off, post time, design, platforms, preview channel and
the approved verse list. Nothing is posted unless the panel says so.

Order within a day:
  1. preview_at (post time minus preview minutes): send image + caption to Slack
  2. post time: publish to each platform not yet posted today, log every result
A failed platform is retried on later runs, at most MAX_ATTEMPTS times a day.
"""
import datetime
from zoneinfo import ZoneInfo

import designs
import post_blessing
from tob_social import publishers
from tob_social.history import FAILED, PUBLISHED

MAX_ATTEMPTS = 3
FALLBACK_DESIGN = "modern_mono"


def parse_time(value):
    """'7:00:00', '07:00:00' or '07:00' -> datetime.time"""
    parts = [int(p) for p in str(value).split(".")[0].split(":")]
    return datetime.time(*(parts + [0] * (3 - len(parts)))[:3])


def choose_verse(verses):
    """Least recently posted approved verse; never-posted first, then by reference, so the pick is stable
    between the preview and the post."""
    usable = [v for v in verses if (v.get("kjv_text") or "").strip()]
    if not usable:
        return None
    return min(usable, key=lambda v: (v.get("last_posted_on") or "", v["reference"]))


class Run:
    def __init__(self, now, cfg, env, history, frappe, slack=None, publisher_factory=publishers.build,
                 out_image=None, dry_run=False):
        self.now, self.cfg, self.env, self.history = now, cfg, env, history
        self.frappe, self.slack, self.build = frappe, slack, publisher_factory
        self.out_image, self.dry_run = out_image, dry_run
        self.today = now.date()
        self.messages = []

    def say(self, text):
        self.messages.append(text)
        print(text)

    def notify(self, text):
        if self.slack and not self.dry_run:
            try:
                self.slack.post(text)
            except Exception as e:  # a Slack problem must never stop posting
                self.say(f"slack: {e}")

    def log(self, event, **fields):
        if self.dry_run:
            return
        try:
            self.frappe.log(event, **fields)
        except Exception as e:  # local history already guards duplicates; the panel log is best-effort
            self.say(f"frappe log failed: {e}")

    def content(self, verse):
        """(verse dict for rendering, caption, design, image path) for an approved panel verse."""
        cfg = self.cfg
        v = {"ref": verse["reference"], "text": verse["kjv_text"].strip()}
        caption = post_blessing.build_message(
            v, {k: cfg[c] for k, c in (("APP_LINK", "app_link"), ("HASHTAGS", "hashtags")) if cfg.get(c)})
        design = cfg.get("design") if cfg.get("design") in designs.STYLES else FALLBACK_DESIGN
        return v, caption, design, designs.render(v, design, self.out_image)

    def test_post(self):
        """Post the next approved verse NOW, ignoring post time, the on/off switch and today's posts —
        for checking the whole chain. Recorded as TEST (history and panel log), so the one-post-a-day
        guard and the verse rotation are unaffected."""
        verse = choose_verse(self.cfg.get("verses", []))
        if not verse:
            return self.say("No approved verse to test with.")
        v, caption, design, image = self.content(verse)
        platforms = self.cfg.get("platforms", [])
        self.say(f"TEST post of {v['ref']} ({design}) to {', '.join(platforms)}.")
        if self.slack:
            try:
                self.slack.upload(image, f"*TEST post* (to be deleted) — posting now to {', '.join(platforms)}.\n\n{caption}")
            except Exception as e:
                self.say(f"slack preview failed: {e}")

        post, results, lines = publishers.Post(caption, image), [], []
        for pub in self.build(platforms, self.env):
            try:
                r = pub.publish(post)
            except publishers.PublishError as e:
                self.history.record(pub.name, self.today, "TEST_FAILED", verse_ref=v["ref"], design=design,
                                    caption=caption, error=str(e), source="test_post")
                self.log("Failed", platform=pub.name, reference=v["ref"], message=f"TEST post: {e}")
                lines.append(f":x: {pub.name}: failed — {str(e)[:300]}")
                results.append({"platform": pub.name, "status": FAILED, "post_id": None, "error": str(e)})
                self.say(f"{pub.name}: FAILED - {e}")
                continue
            post.image_url = post.image_url or r.image_url
            self.history.record(pub.name, self.today, "TEST", verse_ref=v["ref"], design=design, caption=caption,
                                provider_post_id=r.post_id, asset_url=r.image_url, source="test_post")
            # No blessing_verse link, so the panel doesn't count it for rotation.
            self.log("Posted", platform=pub.name, reference=v["ref"], post_id=r.post_id,
                     message="TEST post (manual, to be deleted)")
            lines.append(f":white_check_mark: {pub.name}: posted ({r.post_id})")
            results.append({"platform": pub.name, "status": "TEST", "post_id": r.post_id, "error": None})
            self.say(f"{pub.name}: posted {r.post_id}")
        self.notify(f"*TEST post — {v['ref']}*\n" + "\n".join(lines))
        return results

    def execute(self):
        cfg = self.cfg
        if not cfg.get("enabled"):
            return self.say("Automatic posting is OFF in the control panel.")

        pending = [p for p in cfg.get("platforms", []) if not self.history.published(p, self.today)]
        if not pending:
            return self.say(f"Already posted today to {', '.join(cfg.get('platforms', [])) or 'no platforms'}.")
        retryable = [p for p in pending if self.history.failures(p, self.today) < MAX_ATTEMPTS]
        if not retryable:
            return self.say(f"Gave up for today after {MAX_ATTEMPTS} failed attempts: {', '.join(pending)}.")

        tz = self.now.tzinfo
        post_at = datetime.datetime.combine(self.today, parse_time(cfg.get("post_time", "07:00:00")), tz)
        preview_at = post_at - datetime.timedelta(minutes=cfg.get("preview_minutes_before") or 0)
        if self.now < (preview_at if self.slack else post_at):
            return self.say(f"Nothing due yet (preview {preview_at:%H:%M}, post {post_at:%H:%M}).")

        verse = choose_verse(cfg.get("verses", []))
        if not verse:
            self.say("No approved verse with KJV text in the control panel.")
            if not self.dry_run and self.history.notice_once(self.today, "no_verse"):
                self.log("No Approved Verse", message="Approve at least one TOB Blessing Verse with KJV text.")
                self.notify(":warning: Daily blessing post is ON but no verse is approved. "
                            "Tick 'Checked & approved' on at least one TOB Blessing Verse.")
            return

        v, caption, design, image = self.content(verse)

        preview = self.history.preview(self.today)
        if self.slack and not preview:
            when = "now" if self.now >= post_at else f"at {post_at:%H:%M}"
            self.say(f"Sending Slack preview of {v['ref']} (posting {when}).")
            if not self.dry_run:
                try:
                    self.slack.upload(image, f"*Daily blessing preview* — posts {when} to {', '.join(retryable)}.\n"
                                             f"To stop it: switch *Automatic posting* off in TOB Blessing Automation "
                                             f"Settings, or un-tick the verse's approval.\n\n{caption}")
                    self.history.record_preview(self.today, v["ref"])
                    self.log("Preview Sent", reference=v["ref"], blessing_verse=verse.get("name"))
                except Exception as e:
                    self.say(f"slack preview failed: {e}")
            preview = self.history.preview(self.today)

        if self.now < post_at:
            return self.say(f"Preview done; posting at {post_at:%H:%M}.")
        if self.dry_run:
            return self.say(f"[dry run] Would post {v['ref']} ({design}) to {', '.join(retryable)}.")
        if preview and preview["verse_ref"] != v["ref"]:
            self.notify(f"Note: the verse changed after the preview ({preview['verse_ref']} → {v['ref']}), "
                        "because approvals were edited. Posting the currently approved verse.")

        post = publishers.Post(caption, image)
        results = post_blessing.publish_all(self.build(retryable, self.env), post, self.today, self.history, v, design)
        lines = []
        for r in results:
            if r["status"] == PUBLISHED:
                self.log("Posted", platform=r["platform"], reference=v["ref"], blessing_verse=verse.get("name"),
                         post_id=r["post_id"])
                lines.append(f":white_check_mark: {r['platform']}: posted ({r['post_id']})")
            elif r["status"] == FAILED:
                left = MAX_ATTEMPTS - self.history.failures(r["platform"], self.today)
                self.log("Failed", platform=r["platform"], reference=v["ref"], blessing_verse=verse.get("name"),
                         message=r["error"])
                lines.append(f":x: {r['platform']}: failed — {r['error'][:300]} "
                             f"({'will retry in 15 min' if left > 0 else 'no more retries today'})")
        if lines:
            self.notify(f"*Daily blessing — {v['ref']}*\n" + "\n".join(lines))
        return results


def local_now(env):
    from tob_social.config import DEFAULT_TIMEZONE
    return datetime.datetime.now(ZoneInfo(env.get("TIMEZONE", DEFAULT_TIMEZONE)))
