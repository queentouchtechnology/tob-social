"""Post history in SQLite: what was published where, when, and what failed.

Each post has a `kind` ("blessing", "app_feature", "salvation_prayer", ...). A partial unique index allows
only one PUBLISHED row per platform, kind and day, so a repeated run can never
double-post even if the calling code is wrong.
"""
import datetime
import sqlite3
from pathlib import Path

PUBLISHED = "PUBLISHED"
FAILED = "FAILED"
BLESSING = "blessing"


SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL,
    post_date        TEXT NOT NULL,
    platform         TEXT NOT NULL,
    status           TEXT NOT NULL,
    verse_ref        TEXT,
    design           TEXT,
    caption          TEXT,
    provider_post_id TEXT,
    asset_url        TEXT,
    error            TEXT,
    source           TEXT NOT NULL DEFAULT 'post_blessing',
    kind             TEXT NOT NULL DEFAULT 'blessing'
);
CREATE UNIQUE INDEX IF NOT EXISTS one_publish_per_platform_kind_day
    ON posts (platform, post_date, kind) WHERE status = 'PUBLISHED';
CREATE TABLE IF NOT EXISTS previews (
    post_date TEXT NOT NULL,
    kind      TEXT NOT NULL DEFAULT 'blessing',
    verse_ref TEXT NOT NULL,
    sent_at   TEXT NOT NULL,
    PRIMARY KEY (post_date, kind)
);
CREATE TABLE IF NOT EXISTS notices (
    notice_date TEXT NOT NULL,
    kind        TEXT NOT NULL,
    PRIMARY KEY (notice_date, kind)
);
"""


def _columns(db, table):
    return [row[1] for row in db.execute(f"PRAGMA table_info({table})")]


def _migrate(db):
    """Bring a database from before post kinds existed up to SCHEMA, keeping every row."""
    posts = _columns(db, "posts")
    if posts and "kind" not in posts:
        with db:
            db.execute("ALTER TABLE posts ADD COLUMN kind TEXT NOT NULL DEFAULT 'blessing'")
            db.execute("DROP INDEX IF EXISTS one_publish_per_platform_per_day")
    previews = _columns(db, "previews")
    if previews and "kind" not in previews:
        with db:
            db.execute("ALTER TABLE previews RENAME TO previews_old")
            db.execute("CREATE TABLE previews (post_date TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'blessing', "
                       "verse_ref TEXT NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY (post_date, kind))")
            db.execute("INSERT INTO previews SELECT post_date, 'blessing', verse_ref, sent_at FROM previews_old")
            db.execute("DROP TABLE previews_old")


class History:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        _migrate(self.db)
        self.db.executescript(SCHEMA)

    def published(self, platform, post_date, kind=BLESSING):
        return self.db.execute(
            "SELECT * FROM posts WHERE platform = ? AND post_date = ? AND kind = ? AND status = ?",
            (platform, str(post_date), kind, PUBLISHED),
        ).fetchone()

    def record(self, platform, post_date, status, **fields):
        fields.setdefault("created_at", datetime.datetime.now().isoformat(timespec="seconds"))
        cols = {"platform": platform, "post_date": str(post_date), "status": status, **fields}
        with self.db:
            self.db.execute(
                f"INSERT INTO posts ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                tuple(cols.values()),
            )

    def failures(self, platform, post_date, kind=BLESSING):
        return self.db.execute(
            "SELECT COUNT(*) FROM posts WHERE platform = ? AND post_date = ? AND kind = ? AND status = ?",
            (platform, str(post_date), kind, FAILED),
        ).fetchone()[0]

    def preview(self, post_date, kind=BLESSING):
        return self.db.execute("SELECT * FROM previews WHERE post_date = ? AND kind = ?",
                               (str(post_date), kind)).fetchone()

    def record_preview(self, post_date, verse_ref, kind=BLESSING):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO previews VALUES (?, ?, ?, ?)",
                            (str(post_date), kind, verse_ref, datetime.datetime.now().isoformat(timespec="seconds")))

    def notice_once(self, post_date, kind):
        """True the first time `kind` is raised on this date, False after — for once-a-day alerts."""
        with self.db:
            cur = self.db.execute("INSERT OR IGNORE INTO notices VALUES (?, ?)", (str(post_date), kind))
        return cur.rowcount == 1

    def recent(self, limit=20):
        return self.db.execute("SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def import_legacy_log(self, log_path):
        """Load post_log.txt lines ("<iso time> <platform> <post id> <verse ref>") once; returns rows added.
        The legacy log only ever held blessing posts."""
        log_path = Path(log_path)
        if not log_path.exists():
            return 0
        added = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            parts = line.split(" ", 3)
            if len(parts) < 3:
                continue
            ts, platform, post_id = parts[:3]
            known = self.db.execute("SELECT 1 FROM posts WHERE provider_post_id = ?", (post_id,)).fetchone()
            if known or self.published(platform, ts[:10]):
                continue
            self.record(platform, ts[:10], PUBLISHED, created_at=ts, provider_post_id=post_id,
                        verse_ref=parts[3] if len(parts) > 3 else None, source="post_log.txt")
            added += 1
        return added
