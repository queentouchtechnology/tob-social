"""Common interface every social platform publisher implements.

Adding a platform (Threads, LinkedIn, Google Business Profile, ...) means writing
one Publisher subclass and registering it in publishers/__init__.py.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class PublishError(Exception):
    """A platform rejected or failed a request. The message is safe to log (no tokens)."""


@dataclass
class Post:
    caption: str
    image_path: Path
    image_url: Optional[str] = None  # public URL, for platforms that fetch the image themselves


@dataclass
class Result:
    post_id: str
    image_url: Optional[str] = None  # public URL of the uploaded image, reusable by later platforms


class Publisher:
    name = ""
    needs_public_image = False  # True if the platform needs Post.image_url rather than a file upload

    def check(self):
        """Read-only credential/connection check; returns a short description."""
        raise NotImplementedError

    def publish(self, post):
        """Publish the post and return a Result, or raise PublishError."""
        raise NotImplementedError
