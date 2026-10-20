"""Platform registry. Order matters: platforms that upload a file (and so produce a
public image URL) come before platforms that need one."""
from .base import Post, PublishError, Publisher, Result
from .google import GoogleByHandPublisher
from .meta import FacebookPublisher, InstagramPublisher

ORDER = ["facebook", "instagram"]
BY_HAND = ("google",)  # made by Run itself (Slack + a Frappe link), after the ones that post


def build(names, env):
    """Publishers for the requested platform names, in posting order."""
    names = [n for n in names if n not in BY_HAND]
    unknown = [n for n in names if n not in ORDER]
    if unknown:
        raise ValueError(f"Unknown platform(s): {', '.join(unknown)}. Supported: {', '.join(ORDER)}")
    page_id, token = env.get("FB_PAGE_ID"), env.get("FB_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        raise ValueError("Set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN in .env")
    makers = {
        "facebook": lambda: FacebookPublisher(page_id, token),
        "instagram": lambda: InstagramPublisher(page_id, token),
    }
    return [makers[n]() for n in ORDER if n in names]


__all__ = ["Post", "PublishError", "Publisher", "Result", "build", "ORDER", "BY_HAND", "GoogleByHandPublisher"]
