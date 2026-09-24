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
from tob_social.automation import MAX_ATTEMPTS, Run, choose_verse, parse_time
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

    def log(self, event, **fields):
        self.events.append((event, fields.get("platform")))


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
        self.fail = set()
        self.built = []
        patcher = mock.patch.object(designs, "render", lambda v, s, p: p)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.history.db.close)

    def factory(self, names, env):
        pubs = [FakePublisher(n, n in self.fail) for n in names]
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
        self.fail = {"instagram"}
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
