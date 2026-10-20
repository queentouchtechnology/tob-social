"""Google Business Profile — by hand, until Google approves the Business Profile API for this project.

It doesn't call Google. It puts the post's image and caption in the Slack preview channel with two links: the
profile's "Add update" page (TOB Blessing Automation Settings › Google profile link) and "Mark as posted", a signed
Frappe link that records the post in the TOB Automation Log once someone has put it on Google.
When the API is approved, this publisher is replaced by one that posts — nothing else changes.
"""
from .base import Publisher, PublishError, Result


class GoogleByHandPublisher(Publisher):
    name = "google"

    def __init__(self, slack, post_url, mark_link, label=""):
        """slack: the preview channel (tob_social.slack.Slack); post_url: where to post on Google;
        mark_link: a callable → the signed "Mark as posted" URL for this post (it also logs "Ready to Post")."""
        self.slack, self.post_url, self.mark_link, self.label = slack, post_url, mark_link, label

    def check(self):
        return "Google Business Profile: by hand from Slack"

    def publish(self, post):
        if not self.slack:
            raise PublishError("Google posts go to Slack to be posted by hand — set Slack as the preview channel")
        try:
            done_url = self.mark_link()
        except Exception as e:
            raise PublishError(f"couldn't make the Mark as posted link: {e}") from None
        steps = [
            f":pushpin: *Post this on Google{(' — ' + self.label) if self.label else ''}* (Google Business Profile)",
            f"1. Open {self.post_url or 'https://business.google.com/'} → *Add update*",
            "2. Add the picture above and paste the text below",
            f"3. Then tap: <{done_url}|Mark as posted>",
            "",
            post.caption,
        ]
        try:
            self.slack.upload(post.image_path, "\n".join(steps))
        except Exception as e:
            raise PublishError(f"Slack: {e}") from None
        return Result("by-hand")
