"""Summarise an unexpected HTML response safely for logging (no secrets)."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

_TOKENISH = re.compile(r"[A-Za-z0-9_\-\.=+/]{32,}")


class _Summary(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text: list[str] = []
        self.inputs: list[str] = []
        self.forms: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "input":
            # field names/types only - never values (hidden inputs carry tokens)
            self.inputs.append(f"{a.get('name') or a.get('id') or '?'}:{a.get('type') or 'text'}")
        elif tag == "form":
            self.forms.append(urlsplit(a.get("action") or "").path or "(self)")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        data = data.strip()
        if not data:
            return
        if self._in_title:
            self.title += data
        else:
            self.text.append(data)


def describe_response(resp, max_text: int = 500) -> str:
    """One-line description of a requests.Response: path, status, title, visible text."""
    if resp is None:
        return "no response captured"
    parser = _Summary()
    try:
        parser.feed(resp.text or "")
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        pass
    url = urlsplit(resp.url)
    redirects = " -> ".join(
        f"{urlsplit(r.url).netloc}{urlsplit(r.url).path}" for r in resp.history
    )
    text = _TOKENISH.sub("<redacted>", " ".join(parser.text))[:max_text]
    return (
        f"final={url.netloc}{url.path} status={resp.status_code} "
        f"redirects=[{redirects}] title={parser.title!r} "
        f"forms={parser.forms} inputs={parser.inputs} text={text!r}"
    )
