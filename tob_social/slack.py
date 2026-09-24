"""Slack notifications for approval previews and post results.

Uses the bot token's chat:write and files:write scopes. Image upload follows
Slack's current external-upload flow (getUploadURLExternal -> upload ->
completeUploadExternal); the bot must be a member of the channel for uploads.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://slack.com/api/"


class SlackError(Exception):
    pass


class Slack:
    def __init__(self, token, channel_id, timeout=30):
        if not (token and channel_id):
            raise SlackError("Slack needs SLACK_BOT_TOKEN in .env and a Slack Channel ID in the control panel")
        self.token, self.channel, self.timeout = token, channel_id, timeout

    def _api(self, method, **params):
        req = urllib.request.Request(
            API + method,
            data=urllib.parse.urlencode(params).encode(),
            headers={"Authorization": f"Bearer {self.token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read())
        except urllib.error.URLError as e:
            raise SlackError(f"Slack unreachable: {getattr(e, 'reason', e)}") from None
        if not body.get("ok"):
            hint = " (invite the bot to the channel: /invite @qtt)" if body.get("error") == "not_in_channel" else ""
            raise SlackError(f"Slack {method}: {body.get('error')}{hint}")
        return body

    def post(self, text):
        return self._api("chat.postMessage", channel=self.channel, text=text, unfurl_links="false")

    def upload(self, path, comment):
        data = path.read_bytes()
        target = self._api("files.getUploadURLExternal", filename=path.name, length=len(data))
        req = urllib.request.Request(target["upload_url"], data=data, method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
        try:
            urllib.request.urlopen(req, timeout=self.timeout).close()
        except urllib.error.URLError as e:
            raise SlackError(f"Slack file upload failed: {getattr(e, 'reason', e)}") from None
        return self._api("files.completeUploadExternal", channel_id=self.channel, initial_comment=comment,
                         files=json.dumps([{"id": target["file_id"], "title": path.name}]))
