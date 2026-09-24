"""One run of the scheduled social automation (the systemd timer calls this
every 15 minutes). Every decision comes from the Frappe control panel, read
fresh on each run. Nothing is posted unless the panel says so.

Each kind of post is a Job with its own schedule and rotation:
  - blessing: daily, an approved TOB Blessing Verse (KJV text on a verse image)
  - scheduled content: one job per TOB Automation Schedule row (App Feature,
    Salvation Prayer, ...), on its chosen weekdays, from approved TOB Social
    Content of that type (card design per type, see designs.CONTENT_CARDS)
"Automatic posting ON" is the master switch for all of them.

Order within a day, per job:
  1. preview_at (post time minus preview minutes): send image + caption to Slack
  2. post time: publish to each platform not yet posted today, log every result
A failed platform is retried on later runs, at most MAX_ATTEMPTS times a day.
"""
import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import designs
import post_blessing
from tob_social import publishers
from tob_social.history import BLESSING, FAILED, PUBLISHED

MAX_ATTEMPTS = 3
FALLBACK_DESIGN = "modern_mono"
DEFAULT_HASHTAGS = {
    "App Feature": "#TruthOfBible #BibleApp #BibleStudy",
    "Salvation Prayer": "#TruthOfBible #Jesus #Salvation #Prayer",
}


def parse_time(value):
    """'7:00:00', '07:00:00' or '07:00' -> datetime.time"""
    parts = [int(p) for p in str(value).split(".")[0].split(":")]
    return datetime.time(*(parts + [0] * (3 - len(parts)))[:3])


def _least_recent(items, name_key):
    """Never-posted first, then oldest post, then by name — stable between the preview and the post."""
    return min(items, key=lambda i: (i.get("last_posted_on") or "", i[name_key])) if items else None


def choose_verse(verses):
    return _least_recent([v for v in verses if (v.get("kjv_text") or "").strip()], "reference")


def choose_content(items):
    return _least_recent([i for i in items if (i.get("caption") or "").strip()], "title")


def kind_of(content_type):
    """History key for a content type: 'Salvation Prayer' -> 'salvation_prayer'."""
    return content_type.strip().lower().replace(" ", "_")


def content_caption(item, app_link="", hashtags=""):
    """Caption for a TOB Social Content row, shaped by its type."""
    kind = item.get("content_type")
    hashtags = hashtags or DEFAULT_HASHTAGS.get(kind, "#TruthOfBible")
    if kind == "Salvation Prayer":
        lines = [f"\U0001F64F {item['title']}", "", item["caption"].strip()]
        if app_link:
            lines += ["", f"\U0001F4D6 Keep growing in God's Word with the Truth of Bible app: {app_link}"]
    else:
        lines = [f"✨ {item['title']}", "", item["caption"].strip()]
        if (item.get("how_to_find") or "").strip():
            lines += ["", f"\U0001F4CD In the app: {item['how_to_find'].strip()}"]
        if app_link:
            lines += ["", f"\U0001F4F2 Download Truth of Bible: {app_link}"]
    return "\n".join(lines + ["", hashtags])


@dataclass
class Job:
    kind: str            # history kind: "blessing" | "app_feature" | "salvation_prayer" | ...
    post_type: str       # Frappe log post_type: "Blessing" | "App Feature" | "Salvation Prayer" | ...
    label: str           # human name for messages
    enabled: bool
    off_reason: str
    post_time: str
    item: dict           # the chosen verse/feature, or None
    missing_event: str   # Frappe event when nothing is approved
    missing_notice: str  # Slack text when nothing is approved
    link_field: str      # "blessing_verse" | "social_content"
    ref: str = ""
    hashtags: str = ""


class Run:
    def __init__(self, now, cfg, env, history, frappe, slack=None, publisher_factory=publishers.build,
                 out_image=None, dry_run=False):
        self.now, self.cfg, self.env, self.history = now, cfg, env, history
        self.frappe, self.slack, self.build = frappe, slack, publisher_factory
        self.out_image, self.dry_run = out_image, dry_run
        self.today = now.date()
        self.messages = []

    # -- plumbing -----------------------------------------------------------
    def say(self, text):
        self.messages.append(text)
        print(text)

    def notify(self, text):
        if self.slack and not self.dry_run:
            try:
                self.slack.post(text)
            except Exception as e:  # a Slack problem must never stop posting
                self.say(f"slack: {e}")

    def log(self, event, job=None, **fields):
        if self.dry_run:
            return
        if job:
            fields["post_type"] = job.post_type
            if job.item and job.item.get("name"):
                fields.setdefault(job.link_field, job.item["name"])
        try:
            self.frappe.log(event, **fields)
        except Exception as e:  # local history already guards duplicates; the panel log is best-effort
            self.say(f"frappe log failed: {e}")

    # -- jobs -----------------------------------------------------------------
    def jobs(self):
        cfg = self.cfg
        master = bool(cfg.get("enabled"))
        verse = choose_verse(cfg.get("verses", []))
        blessing = Job(
            kind=BLESSING, post_type="Blessing", label="Daily blessing",
            enabled=master, off_reason="Automatic posting is OFF in the control panel.",
            post_time=cfg.get("post_time") or "07:00:00", item=verse,
            missing_event="No Approved Verse",
            missing_notice=":warning: Daily blessing post is ON but no verse is approved. "
                           "Tick 'Checked & approved' on at least one TOB Blessing Verse.",
            link_field="blessing_verse", ref=verse["reference"] if verse else "")

        jobs = [blessing]
        for sched in cfg.get("schedules") or []:
            kind = sched["content_type"]
            item = choose_content(sched.get("items", []))
            on_today = self.today.weekday() in (sched.get("weekdays") or [])
            jobs.append(Job(
                kind=kind_of(kind), post_type=kind, label=kind,
                enabled=master and bool(sched.get("enabled")) and on_today,
                off_reason=(f"{kind} posts are OFF." if not (master and sched.get("enabled"))
                            else f"Not a {kind.lower()} day."),
                post_time=sched.get("post_time") or "18:00:00", item=item,
                missing_event="No Approved Content",
                missing_notice=f":warning: {kind} posts are ON but nothing of that type is approved. "
                               f"Tick 'Checked & approved' on at least one {kind} in TOB Social Content.",
                link_field="social_content", ref=item["title"] if item else "",
                hashtags=sched.get("hashtags") or ""))
        return jobs

    def content(self, job):
        """(caption, design, image path) for the job's chosen item."""
        cfg = self.cfg
        if job.kind != BLESSING:
            caption = content_caption(job.item, cfg.get("app_link", ""), job.hashtags)
            return caption, job.kind, designs.render_content(job.item, self.out_image)
        v = {"ref": job.item["reference"], "text": job.item["kjv_text"].strip()}
        caption = post_blessing.build_message(
            v, {k: cfg[c] for k, c in (("APP_LINK", "app_link"), ("HASHTAGS", "hashtags")) if cfg.get(c)})
        design = cfg.get("design") if cfg.get("design") in designs.STYLES else FALLBACK_DESIGN
        return caption, design, designs.render(v, design, self.out_image)

    def execute(self):
        results = []
        for job in self.jobs():
            out = self.run_job(job)
            if isinstance(out, list):
                results += out
        return results

    def run_job(self, job):
        platforms = self.cfg.get("platforms", [])
        if not job.enabled:
            return self.say(f"{job.label}: {job.off_reason}")

        pending = [p for p in platforms if not self.history.published(p, self.today, job.kind)]
        if not pending:
            return self.say(f"{job.label}: already posted today to {', '.join(platforms) or 'no platforms'}.")
        retryable = [p for p in pending if self.history.failures(p, self.today, job.kind) < MAX_ATTEMPTS]
        if not retryable:
            return self.say(f"{job.label}: gave up for today after {MAX_ATTEMPTS} failed attempts: "
                            f"{', '.join(pending)}.")

        tz = self.now.tzinfo
        post_at = datetime.datetime.combine(self.today, parse_time(job.post_time), tz)
        preview_at = post_at - datetime.timedelta(minutes=self.cfg.get("preview_minutes_before") or 0)
        if self.now < (preview_at if self.slack else post_at):
            return self.say(f"{job.label}: nothing due yet (preview {preview_at:%H:%M}, post {post_at:%H:%M}).")

        if not job.item:
            self.say(f"{job.label}: nothing approved in the control panel.")
            if not self.dry_run and self.history.notice_once(self.today, f"no_{job.kind}"):
                self.log(job.missing_event, job, message="Nothing approved to post.")
                self.notify(job.missing_notice)
            return

        caption, design, image = self.content(job)
        preview = self.history.preview(self.today, job.kind)
        if self.slack and not preview:
            when = "now" if self.now >= post_at else f"at {post_at:%H:%M}"
            self.say(f"{job.label}: sending Slack preview of {job.ref} (posting {when}).")
            if not self.dry_run:
                try:
                    self.slack.upload(image, f"*{job.label} preview* — posts {when} to {', '.join(retryable)}.\n"
                                             f"To stop it: switch posting off in TOB Blessing Automation "
                                             f"Settings, or un-tick its approval.\n\n{caption}")
                    self.history.record_preview(self.today, job.ref, job.kind)
                    self.log("Preview Sent", job, reference=job.ref)
                except Exception as e:
                    self.say(f"slack preview failed: {e}")
            preview = self.history.preview(self.today, job.kind)

        if self.now < post_at:
            return self.say(f"{job.label}: preview done; posting at {post_at:%H:%M}.")
        if self.dry_run:
            return self.say(f"[dry run] {job.label}: would post {job.ref} ({design}) to {', '.join(retryable)}.")
        if preview and preview["verse_ref"] != job.ref:
            self.notify(f"Note: the {job.label.lower()} changed after the preview ({preview['verse_ref']} → "
                        f"{job.ref}), because approvals were edited. Posting the currently approved one.")

        results = post_blessing.publish_all(self.build(retryable, self.env), publishers.Post(caption, image),
                                            self.today, self.history, {"ref": job.ref}, design, kind=job.kind)
        lines = []
        for r in results:
            if r["status"] == PUBLISHED:
                self.log("Posted", job, platform=r["platform"], reference=job.ref, post_id=r["post_id"])
                lines.append(f":white_check_mark: {r['platform']}: posted ({r['post_id']})")
            elif r["status"] == FAILED:
                left = MAX_ATTEMPTS - self.history.failures(r["platform"], self.today, job.kind)
                self.log("Failed", job, platform=r["platform"], reference=job.ref, message=r["error"])
                lines.append(f":x: {r['platform']}: failed — {r['error'][:300]} "
                             f"({'will retry in 15 min' if left > 0 else 'no more retries today'})")
        if lines:
            self.notify(f"*{job.label} — {job.ref}*\n" + "\n".join(lines))
        return results

    def test_post(self, kind=BLESSING):
        """Post the next approved verse (or content of `kind`, e.g. "salvation_prayer") NOW, ignoring post time, switches and today's posts —
        for checking the whole chain. Recorded as TEST (history and panel log, with no verse/feature
        link), so the one-post-a-day guard and the rotation are unaffected."""
        job = next((j for j in self.jobs() if j.kind == kind), None)
        if job is None:
            return self.say(f"No schedule row for '{kind}' in the control panel.")
        if not job.item:
            return self.say(f"No approved {job.label.lower()} to test with.")
        caption, design, image = self.content(job)
        platforms = self.cfg.get("platforms", [])
        self.say(f"TEST post of {job.ref} ({design}) to {', '.join(platforms)}.")
        if self.slack:
            try:
                self.slack.upload(image, f"*TEST {job.label.lower()} post* (to be deleted) — posting now to "
                                         f"{', '.join(platforms)}.\n\n{caption}")
            except Exception as e:
                self.say(f"slack preview failed: {e}")

        post, results, lines = publishers.Post(caption, image), [], []
        for pub in self.build(platforms, self.env):
            try:
                r = pub.publish(post)
            except publishers.PublishError as e:
                self.history.record(pub.name, self.today, "TEST_FAILED", verse_ref=job.ref, design=design,
                                    caption=caption, error=str(e), source="test_post", kind=job.kind)
                self.log("Failed", platform=pub.name, reference=job.ref, post_type=job.post_type,
                         message=f"TEST post: {e}")
                lines.append(f":x: {pub.name}: failed — {str(e)[:300]}")
                results.append({"platform": pub.name, "status": FAILED, "post_id": None, "error": str(e)})
                self.say(f"{pub.name}: FAILED - {e}")
                continue
            post.image_url = post.image_url or r.image_url
            self.history.record(pub.name, self.today, "TEST", verse_ref=job.ref, design=design, caption=caption,
                                provider_post_id=r.post_id, asset_url=r.image_url, source="test_post",
                                kind=job.kind)
            # No verse/feature link, so the panel doesn't count it for rotation or the report.
            self.log("Posted", platform=pub.name, reference=job.ref, post_type=job.post_type, post_id=r.post_id,
                     message="TEST post (manual, to be deleted)")
            lines.append(f":white_check_mark: {pub.name}: posted ({r.post_id})")
            results.append({"platform": pub.name, "status": "TEST", "post_id": r.post_id, "error": None})
            self.say(f"{pub.name}: posted {r.post_id}")
        self.notify(f"*TEST {job.label.lower()} post — {job.ref}*\n" + "\n".join(lines))
        return results


def local_now(env):
    from tob_social.config import DEFAULT_TIMEZONE
    return datetime.datetime.now(ZoneInfo(env.get("TIMEZONE", DEFAULT_TIMEZONE)))
