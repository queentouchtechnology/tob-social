"""Client for the control panel in the truthofbible-ai Frappe app
(truth_of_bible.social.blessing_automation). Authenticates as a dedicated API
user holding only the `TOB Social Worker` role."""
import json
import urllib.error
import urllib.request

METHOD_PREFIX = "truth_of_bible.social.blessing_automation."


class FrappeError(Exception):
    pass


class FrappeClient:
    def __init__(self, url, api_key, api_secret, timeout=30):
        if not (url and api_key and api_secret):
            raise FrappeError("Set FRAPPE_URL, FRAPPE_API_KEY and FRAPPE_API_SECRET in .env")
        self.url, self.timeout = url.rstrip("/"), timeout
        self.auth = f"token {api_key}:{api_secret}"

    def call(self, method, **params):
        req = urllib.request.Request(
            f"{self.url}/api/method/{METHOD_PREFIX}{method}",
            data=json.dumps(params).encode(),
            method="POST",
            headers={"Authorization": self.auth, "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read()).get("message")
        except urllib.error.HTTPError as e:
            raise FrappeError(f"Frappe {method} failed ({e.code}): {e.read().decode()[:500]}") from None
        except urllib.error.URLError as e:
            raise FrappeError(f"Frappe unreachable: {e.reason}") from None

    def config(self):
        return self.call("get_worker_config")

    def log(self, event, **fields):
        return self.call("log_event", event=event, **fields)

    def import_verse_texts(self, verses):
        return self.call("import_verse_texts", verses=verses)
