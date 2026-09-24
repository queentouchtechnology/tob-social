"""Scheduled-run decisions, with fake Frappe/Slack/platform clients — no network."""
import contextlib
import datetime
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import designs
from tob_social import publishers
from tob_social.automation import MAX_ATTEMPTS, Run, choose_content, choose_verse, content_caption, kind_of, parse_time
from tob_social.history import History

IST = ZoneInfo("Asia/Kolkata")
DAY = datetime.date(2026, 9, 25)


def at(hh, mm):
    return datetime.datetime(2026, 9, 25, hh, mm, tzinfo=IST)


def config(**overrides):
    cfg = {
        "enabled": True, "post_time": "7:00:00", "design": "modern_mono", "platforms": ["facebook", "instagram"],
        "preview_channel": "Slack", "slack_channel_id": "C1", "preview_minutes_before": 60,
        "app_link": "https://app", "hashtags": "#TOB",
        "verses": [{"name": "v1", "reference": "Numbers 6:24-26", "kjv_text": "The LORD bless thee", "last_posted_on": None}],
    }
    cfg.update(overrides)
    return cfg


class FakeFrappe:
    def __init__(self):
        self.events = []
        self.fields = []

    def log(self, event, **fields):
        self.events.append((event, fields.get("platform")))
        self.fields.append((event, fields))


class FakeSlack:
    def __init__(self):
        self.posts, self.uploads = [], []

    def post(self, text):
        self.posts.append(text)

    def upload(self, path, comment):
        self.uploads.append(comment)


class FakePublisher(publishers.Publisher):
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, 0

    def publish(self, post):
        self.calls += 1
        if self.fail:
            raise publishers.PublishError(f"{self.name} down")
        return publishers.Result(f"{self.name}-1", "https://cdn/img.png")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.history = History(self.dir / "h.db")
        self.frappe, self.slack = FakeFrappe(), FakeSlack()
        self.failing = set()
        self.built = []
        for name, fake in (("render", lambda v, s, p: p), ("render_content", lambda i, p: p)):
            patcher = mock.patch.object(designs, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.history.db.close)

    def factory(self, names, env):
        pubs = [FakePublisher(n, n in self.failing) for n in names]
        self.built.append(pubs)
        return pubs

    def run_at(self, when, cfg=None, slack=True, dry_run=False):
        run = Run(when, cfg or config(), {}, self.history, self.frappe, self.slack if slack else None,
                  self.factory, out_image=self.dir / "today.png", dry_run=dry_run)
        with contextlib.redirect_stdout(io.StringIO()), mock.patch("post_blessing.log"):
            return run.execute()

    def events(self):
        return [e for e, _ in self.frappe.events]


class Switch(Base):
    def test_off_does_nothing(self):
        self.run_at(at(7, 5), config(enabled=False))
        self.assertEqual((self.events(), self.slack.posts, self.slack.uploads, self.built), ([], [], [], []))


class Timing(Base):
    def test_before_preview_time_nothing_happens(self):
        self.run_at(at(5, 59))
        self.assertEqual((self.slack.uploads, self.built), ([], []))

    def test_preview_sent_once_and_nothing_posted(self):
        self.run_at(at(6, 0))
        self.run_at(at(6, 15))
        self.assertEqual(len(self.slack.uploads), 1)
        self.assertIn("The LORD bless thee", self.slack.uploads[0])
        self.assertEqual(self.events(), ["Preview Sent"])
        self.assertEqual(self.built, [])

    def test_posts_at_post_time_and_logs_each_platform(self):
        self.run_at(at(6, 0))
        self.run_at(at(7, 0))
        self.assertEqual(self.events(), ["Preview Sent", "Posted", "Posted"])
        self.assertEqual(len(self.slack.posts), 1)  # result summary

    def test_nothing_after_posting(self):
        self.run_at(at(7, 0))
        self.run_at(at(7, 15))
        self.assertEqual(len(self.built), 1)

    def test_late_start_previews_and_posts_same_run(self):
        self.run_at(at(9, 30))
        self.assertEqual(self.events(), ["Preview Sent", "Posted", "Posted"])

    def test_without_slack_posts_at_post_time_without_preview(self):
        self.run_at(at(6, 30), slack=False)
        self.assertEqual(self.built, [])
        self.run_at(at(7, 0), slack=False)
        self.assertEqual(self.events(), ["Posted", "Posted"])


class Failures(Base):
    def test_failed_platform_retried_then_given_up(self):
        self.failing = {"instagram"}
        for minute in range(0, 15 * (MAX_ATTEMPTS + 2), 15):
            self.run_at(at(7, 0) + datetime.timedelta(minutes=minute))
        self.assertEqual(self.events().count("Failed"), MAX_ATTEMPTS)
        self.assertEqual(self.events().count("Posted"), 1)  # facebook once, never re-posted

    def test_no_approved_verse_alerts_once_a_day(self):
        cfg = config(verses=[])
        self.run_at(at(7, 0), cfg)
        self.run_at(at(7, 15), cfg)
        self.assertEqual(self.events(), ["No Approved Verse"])
        self.assertEqual(len(self.slack.posts), 1)

    def test_no_verse_alert_waits_until_preview_time(self):
        cfg = config(verses=[])
        self.run_at(at(0, 0), cfg)
        self.assertEqual((self.events(), self.slack.posts), ([], []))
        self.run_at(at(6, 0), cfg)
        self.assertEqual(self.events(), ["No Approved Verse"])

    def test_dry_run_sends_and_logs_nothing(self):
        self.run_at(at(7, 0), dry_run=True)
        self.assertEqual((self.events(), self.slack.posts, self.slack.uploads, self.built), ([], [], [], []))


class TestPost(Base):
    def test_posts_even_after_todays_post_without_touching_the_guard(self):
        self.run_at(at(7, 0))  # the real post for today
        run = Run(at(22, 0), config(enabled=False), {}, self.history, self.frappe, self.slack, self.factory,
                  out_image=self.dir / "today.png")
        with contextlib.redirect_stdout(io.StringIO()):
            results = run.test_post()
        self.assertEqual([r["status"] for r in results], ["TEST", "TEST"])
        self.assertEqual(self.history.published("facebook", DAY)["provider_post_id"], "facebook-1")
        self.assertIn("TEST daily blessing post", self.slack.uploads[-1])
        self.run_at(at(22, 15))  # a normal run afterwards still sees today as done
        self.assertEqual(len(self.built), 2)


FEATURE_ITEM = {"name": "f1", "content_type": "App Feature", "title": "Gospel Compare",
                "image_text": "Side by side.", "image_footer": "", "caption": "Read them together.",
                "how_to_find": "Explore → Gospel Compare", "last_posted_on": None}
PRAYER_ITEM = {"name": "p1", "content_type": "Salvation Prayer", "title": "God So Loved You",
               "image_text": "Father, thank You...", "image_footer": "John 3:16", "caption": "Whosoever.",
               "how_to_find": "", "last_posted_on": None}


def schedule(content_type, items, on=True, weekdays=(DAY.weekday(),), post_time="18:00:00"):
    return {"content_type": content_type, "enabled": on, "post_time": post_time, "weekdays": list(weekdays),
            "hashtags": "", "items": list(items)}


def with_schedules(*schedules, **overrides):
    return config(schedules=list(schedules), **overrides)


class ScheduledContent(Base):
    def test_feature_posts_at_its_own_time_after_the_blessing(self):
        cfg = with_schedules(schedule("App Feature", [FEATURE_ITEM]))
        self.run_at(at(7, 0), cfg)   # blessing
        self.run_at(at(17, 0), cfg)  # feature preview
        self.run_at(at(18, 0), cfg)  # feature post
        self.assertEqual(self.events(), ["Preview Sent", "Posted", "Posted", "Preview Sent", "Posted", "Posted"])
        self.assertIsNotNone(self.history.published("facebook", DAY, "app_feature"))
        posts = [f for e, f in self.frappe.fields if e == "Posted" and f.get("post_type") == "App Feature"]
        self.assertEqual({f["social_content"] for f in posts}, {"f1"})
        self.assertTrue(all("blessing_verse" not in f for f in posts))

    def test_three_kinds_same_day_are_independent(self):
        cfg = with_schedules(schedule("App Feature", [FEATURE_ITEM], post_time="12:00:00"),
                             schedule("Salvation Prayer", [PRAYER_ITEM], post_time="20:00:00"))
        for hh in (7, 12, 20):
            self.run_at(at(hh, 0), cfg)
        self.assertEqual(self.events().count("Posted"), 6)
        for kind in ("blessing", "app_feature", "salvation_prayer"):
            self.assertIsNotNone(self.history.published("instagram", DAY, kind), kind)
        prayer = [f for e, f in self.frappe.fields if e == "Posted" and f.get("post_type") == "Salvation Prayer"]
        self.assertEqual({f["social_content"] for f in prayer}, {"p1"})

    def test_not_a_scheduled_day(self):
        self.run_at(at(18, 0), with_schedules(schedule("App Feature", [FEATURE_ITEM],
                                                       weekdays=[(DAY.weekday() + 1) % 7])))
        self.assertEqual(self.events(), ["Preview Sent", "Posted", "Posted"])  # blessing only

    def test_schedule_row_off(self):
        self.run_at(at(18, 0), with_schedules(schedule("App Feature", [FEATURE_ITEM], on=False)))
        self.assertEqual(self.events(), ["Preview Sent", "Posted", "Posted"])

    def test_master_switch_stops_scheduled_content_too(self):
        self.run_at(at(18, 0), with_schedules(schedule("App Feature", [FEATURE_ITEM]), enabled=False))
        self.assertEqual(self.events(), [])

    def test_nothing_approved_alerts_once_per_type(self):
        cfg = with_schedules(schedule("App Feature", []), schedule("Salvation Prayer", []))
        self.run_at(at(18, 0), cfg)
        self.run_at(at(18, 15), cfg)
        self.assertEqual(self.events().count("No Approved Content"), 2)

    def test_content_test_post_is_unlinked(self):
        run = Run(at(10, 0), with_schedules(schedule("Salvation Prayer", [PRAYER_ITEM])), {}, self.history,
                  self.frappe, self.slack, self.factory, out_image=self.dir / "today.png")
        with contextlib.redirect_stdout(io.StringIO()):
            results = run.test_post("salvation_prayer")
        self.assertEqual([r["status"] for r in results], ["TEST", "TEST"])
        self.assertTrue(all("social_content" not in f for _, f in self.frappe.fields))
        self.assertIsNone(self.history.published("facebook", DAY, "salvation_prayer"))

    def test_test_post_unknown_kind(self):
        run = Run(at(10, 0), config(), {}, self.history, self.frappe, self.slack, self.factory,
                  out_image=self.dir / "today.png")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(run.test_post("app_feature"))
        self.assertEqual(self.built, [])


class Captions(unittest.TestCase):
    def test_feature_caption(self):
        text = content_caption(FEATURE_ITEM, "https://app", "#App")
        for part in ("Gospel Compare", "Read them together.", "In the app: Explore → Gospel Compare",
                     "https://app", "#App"):
            self.assertIn(part, text)

    def test_prayer_caption_uses_type_defaults(self):
        text = content_caption(PRAYER_ITEM, "https://app")
        self.assertIn("God So Loved You", text)
        self.assertIn("#Salvation", text)
        self.assertNotIn("In the app", text)

    def test_choose_content_needs_caption(self):
        self.assertIsNone(choose_content([{**FEATURE_ITEM, "caption": " "}]))

    def test_kind_of(self):
        self.assertEqual(kind_of("Salvation Prayer"), "salvation_prayer")


class VerseChoice(unittest.TestCase):
    def test_never_posted_first_then_oldest(self):
        verses = [
            {"reference": "B 1:1", "kjv_text": "b", "last_posted_on": "2026-09-01"},
            {"reference": "A 1:1", "kjv_text": "a", "last_posted_on": "2026-09-10"},
            {"reference": "C 1:1", "kjv_text": "c", "last_posted_on": None},
        ]
        self.assertEqual(choose_verse(verses)["reference"], "C 1:1")
        verses[2]["last_posted_on"] = "2026-09-24"
        self.assertEqual(choose_verse(verses)["reference"], "B 1:1")

    def test_verse_without_text_ignored(self):
        self.assertIsNone(choose_verse([{"reference": "A 1:1", "kjv_text": " ", "last_posted_on": None}]))


class TimeParsing(unittest.TestCase):
    def test_formats(self):
        for value in ("7:00:00", "07:00:00", "07:00", "7:00:00.000000"):
            with self.subTest(value=value):
                self.assertEqual(parse_time(value), datetime.time(7, 0))


if __name__ == "__main__":
    unittest.main()
