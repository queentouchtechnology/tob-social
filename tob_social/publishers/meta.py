"""Facebook Page and Instagram publishing through the Meta Graph API."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .base import PublishError, Publisher, Result

GRAPH = "https://graph.facebook.com/v23.0"


def graph(path, params, method="GET", files=None):
    url = f"{GRAPH}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
    elif files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in params.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, p in files.items():
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{p.name}"\r\n'
                     f"Content-Type: image/png\r\n\r\n").encode() + p.read_bytes() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # The error body comes from Meta and never echoes the access token.
        raise PublishError(f"Graph API error {e.code} on {path.split('?')[0]}: {e.read().decode()}") from None
    except urllib.error.URLError as e:
        raise PublishError(f"Network error on {path}: {e.reason}") from None


class FacebookPublisher(Publisher):
    name = "facebook"

    def __init__(self, page_id, token):
        self.page_id, self.token = page_id, token

    def check(self):
        page = graph(self.page_id, {"fields": "id,name", "access_token": self.token})
        return f"Page {page['name']} ({page['id']})"

    def publish(self, post):
        photo = graph(f"{self.page_id}/photos", {"caption": post.caption, "access_token": self.token},
                      "POST", {"source": post.image_path})
        # Largest rendition of the uploaded photo; Instagram fetches the image from this public URL.
        images = graph(photo["id"], {"fields": "images", "access_token": self.token})["images"]
        return Result(photo.get("post_id") or photo["id"], max(images, key=lambda i: i["width"])["source"])


class InstagramPublisher(Publisher):
    name = "instagram"
    needs_public_image = True

    def __init__(self, page_id, token, poll_seconds=2):
        self.page_id, self.token, self.poll_seconds = page_id, token, poll_seconds
        self._ig_id = None

    def ig_id(self):
        if not self._ig_id:
            page = graph(self.page_id, {"fields": "instagram_business_account", "access_token": self.token})
            self._ig_id = (page.get("instagram_business_account") or {}).get("id")
            if not self._ig_id:
                raise PublishError("No Instagram business account is linked to this Facebook Page")
        return self._ig_id

    def check(self):
        return f"Instagram account {self.ig_id()}"

    def publish(self, post):
        if not post.image_url:
            raise PublishError("Instagram needs a public image URL (post to Facebook first)")
        ig = self.ig_id()
        container = graph(f"{ig}/media", {"image_url": post.image_url, "caption": post.caption,
                                          "access_token": self.token}, "POST")
        for _ in range(30):
            status = graph(container["id"], {"fields": "status_code", "access_token": self.token})["status_code"]
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise PublishError("Instagram could not process the image")
            time.sleep(self.poll_seconds)
        else:
            raise PublishError("Instagram image processing timed out")
        media = graph(f"{ig}/media_publish", {"creation_id": container["id"], "access_token": self.token}, "POST")
        return Result(media["id"])
