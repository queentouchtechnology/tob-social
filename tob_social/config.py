"""Settings loaded from the .env file in the project root."""
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_PLATFORMS = "facebook,instagram"


def load_env(path=ROOT / ".env"):
    env = {}
    path = Path(path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"')
    return env


def local_today(env):
    """Today's date in the ministry's time zone, so a VPS in another zone posts on the right day."""
    return datetime.datetime.now(ZoneInfo(env.get("TIMEZONE", DEFAULT_TIMEZONE))).date()


def platforms(env):
    return [p.strip().lower() for p in env.get("PLATFORMS", DEFAULT_PLATFORMS).split(",") if p.strip()]
