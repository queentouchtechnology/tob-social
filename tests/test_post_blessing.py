"""Tests for the current posting workflow. No test touches the network:
publishers are replaced with fakes, and urlopen is patched to fail loudly."""
import contextlib
import datetime
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import designs
import post_blessing
from tob_social import config, publishers
from tob_social.history import FAILED, PUBLISHED, History
from tob_social.publishers import meta

ROOT = Path(__file__).resolve().parent.parent
VERSES = json.loads((ROOT / "verses.json").read_text(encoding="utf-8"))
TODAY = datetime.date(2026, 9, 24)


def no_network(*a, **k):
    raise AssertionError("test attempted a real network call")


class FakePublisher(publishers.Publisher):
    def __init__(self, name, needs_public_image=False, fail=False):
        self.name, self.needs_public_image, self.fail = name, needs_public_image, fail
        self.calls = []

    def publish(self, post):
        self.calls.append(post.image_url)
        if self.fail:
            raise publishers.PublishError(f"{self.name} is down")
        if self.needs_public_image and not post.image_url:
            raise publishers.PublishError("needs a public image URL")
        return publishers.Result(f"{self.name}-id", "https://cdn.example/img.png" if self.name == "facebook" else None)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.history = History(self.dir / "h.db")
        self.log = self.dir / "post_log.txt"

    def tearDown(self):
        self.history.db.close()

    def post(self, *pubs):
        post = publishers.Post("caption", self.dir / "img.png")
        with contextlib.redirect_stdout(io.StringIO()):
            results = post_blessing.publish_all(list(pubs), post, TODAY, self.history, VERSES[0], "modern_mono", self.log)
        return sum(r["status"] == FAILED for r in results)


class VerseAndCaption(unittest.TestCase):
    def test_same_date_same_verse(self):
        self.assertEqual(post_blessing.todays_verse(TODAY), post_blessing.todays_verse(TODAY))

    def test_consecutive_days_differ_including_new_year(self):
        for day in [TODAY, datetime.date(2026, 12, 31)]:
            nxt = day + datetime.timedelta(days=1)
            self.assertNotEqual(post_blessing.todays_verse(day)["ref"], post_blessing.todays_verse(nxt)["ref"])

    def test_caption_has_verse_reference_link_and_hashtags(self):
        msg = post_blessing.build_message(VERSES[0], {"APP_LINK": "https://app", "HASHTAGS": "#A #B"})
        self.assertIn(VERSES[0]["text"], msg)
        self.assertIn(f"{VERSES[0]['ref']} (KJV)", msg)
        self.assertIn("https://app", msg)
        self.assertTrue(msg.endswith("#A #B"))

    def test_verses_have_ref_and_text(self):
        for v in VERSES:
            self.assertTrue(v["ref"] and v["text"], v)


class Designs(unittest.TestCase):
    def test_every_style_renders_square_for_short_and_long_verses(self):
        by_len = sorted(VERSES, key=lambda v: len(v["text"]))
        for verse in (by_len[0], by_len[-1]):
            for name, fn in designs.STYLES.items():
                with self.subTest(style=name, ref=verse["ref"]):
                    self.assertEqual(fn(verse).size, (1080, 1080))


class Config(unittest.TestCase):
    def test_platforms_default_and_override(self):
        self.assertEqual(config.platforms({}), ["facebook", "instagram"])
        self.assertEqual(config.platforms({"PLATFORMS": " Facebook "}), ["facebook"])

    def test_local_today_uses_timezone(self):
        self.assertIsInstance(config.local_today({"TIMEZONE": "Asia/Kolkata"}), datetime.date)

    def test_unknown_platform_rejected(self):
        with self.assertRaises(ValueError):
            publishers.build(["myspace"], {"FB_PAGE_ID": "1", "FB_PAGE_ACCESS_TOKEN": "t"})

    def test_missing_credentials_rejected(self):
        with self.assertRaises(ValueError):
            publishers.build(["facebook"], {})

    def test_build_keeps_posting_order(self):
        pubs = publishers.build(["instagram", "facebook"], {"FB_PAGE_ID": "1", "FB_PAGE_ACCESS_TOKEN": "t"})
        self.assertEqual([p.name for p in pubs], ["facebook", "instagram"])


class Publishing(Tmp):
    def test_posts_facebook_then_instagram_with_public_url(self):
        fb, ig = FakePublisher("facebook"), FakePublisher("instagram", needs_public_image=True)
        self.assertEqual(self.post(fb, ig), 0)
        self.assertEqual(ig.calls, ["https://cdn.example/img.png"])
        self.assertEqual(self.history.published("instagram", TODAY)["provider_post_id"], "instagram-id")
        self.assertEqual(len(self.log.read_text().splitlines()), 2)

    def test_second_run_same_day_posts_nothing(self):
        self.post(FakePublisher("facebook"), FakePublisher("instagram", True))
        fb, ig = FakePublisher("facebook"), FakePublisher("instagram", True)
        self.assertEqual(self.post(fb, ig), 0)
        self.assertEqual((fb.calls, ig.calls), ([], []))

    def test_retry_after_instagram_failure_reuses_facebook_image(self):
        self.assertEqual(self.post(FakePublisher("facebook"), FakePublisher("instagram", True, fail=True)), 1)
        fb, ig = FakePublisher("facebook"), FakePublisher("instagram", True)
        self.assertEqual(self.post(fb, ig), 0)
        self.assertEqual(fb.calls, [])
        self.assertEqual(ig.calls, ["https://cdn.example/img.png"])

    def test_failure_is_recorded(self):
        self.post(FakePublisher("facebook", fail=True))
        row = self.history.recent(1)[0]
        self.assertEqual((row["status"], row["error"]), (FAILED, "facebook is down"))

    def test_database_refuses_second_publish_same_day(self):
        self.history.record("facebook", TODAY, PUBLISHED, provider_post_id="a")
        with self.assertRaises(Exception):
            self.history.record("facebook", TODAY, PUBLISHED, provider_post_id="b")


class LegacyLog(Tmp):
    def test_import_is_idempotent(self):
        self.log.write_text("2026-09-24T19:30:02 facebook 1_2 Jeremiah 17:7\n"
                            "2026-09-24T19:30:12 instagram 3 Jeremiah 17:7\n", encoding="utf-8")
        self.assertEqual(self.history.import_legacy_log(self.log), 2)
        self.assertEqual(self.history.import_legacy_log(self.log), 0)
        self.assertEqual(self.history.published("facebook", TODAY)["verse_ref"], "Jeremiah 17:7")


class DryRun(unittest.TestCase):
    @mock.patch("urllib.request.urlopen", no_network)
    def test_dry_run_sends_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(post_blessing, "HISTORY_DB", tmp / "h.db"), \
                mock.patch.object(post_blessing, "LEGACY_LOG", tmp / "log.txt"), \
                mock.patch.object(post_blessing, "HERE", ROOT), \
                mock.patch.object(designs, "render", lambda v, s, p: p), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(post_blessing.main([]), 0)
        self.assertIn("[dry run] Nothing posted", out.getvalue())
        self.assertFalse((tmp / "log.txt").exists())


class MetaPublishers(unittest.TestCase):
    def test_instagram_needs_public_url(self):
        ig = meta.InstagramPublisher("page", "token")
        with self.assertRaises(publishers.PublishError):
            ig.publish(publishers.Post("c", Path("x.png")))

    def test_instagram_flow_uses_graph_in_order(self):
        calls = []

        def fake_graph(path, params, method="GET", files=None):
            calls.append((method, path))
            return {"page": {"instagram_business_account": {"id": "ig"}},
                    "ig/media": {"id": "c1"}, "c1": {"status_code": "FINISHED"},
                    "ig/media_publish": {"id": "m1"}}[path]

        with mock.patch.object(meta, "graph", fake_graph):
            result = meta.InstagramPublisher("page", "token").publish(
                publishers.Post("c", Path("x.png"), "https://cdn/img.png"))
        self.assertEqual(result.post_id, "m1")
        self.assertEqual(calls, [("GET", "page"), ("POST", "ig/media"), ("GET", "c1"), ("POST", "ig/media_publish")])

    def test_graph_errors_become_publish_errors(self):
        import urllib.error
        err = urllib.error.URLError("offline")
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(publishers.PublishError):
                meta.graph("x", {"access_token": "secret"})


if __name__ == "__main__":
    unittest.main()
