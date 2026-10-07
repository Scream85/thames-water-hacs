"""Diagnostics: a safe summary of an unexpected page for logs, and the download for bug reports.

Nothing here may contain a credential, the account number or the full meter id.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, is_dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import ThamesWaterConfigEntry

_TOKENISH = re.compile(r"[A-Za-z0-9_\-\.=+/]{32,}")

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


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
    redirects = " -> ".join(f"{urlsplit(r.url).netloc}{urlsplit(r.url).path}" for r in resp.history)
    text = _TOKENISH.sub("<redacted>", " ".join(parser.text))[:max_text]
    return (
        f"final={url.netloc}{url.path} status={resp.status_code} "
        f"redirects=[{redirects}] title={parser.title!r} "
        f"forms={parser.forms} inputs={parser.inputs} text={text!r}"
    )


def _mask(value: object) -> str:
    """Enough of an identifier to tell two apart in a bug report, not enough to use it."""
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return f"{'*' * (len(text) - 2)}{text[-2:]}"


def _jsonable(value: Any) -> Any:
    """Turn dataclasses, dates and datetimes into plain JSON types."""
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ThamesWaterConfigEntry
) -> dict[str, Any]:
    """Everything useful for a bug report, with credentials and identifiers removed."""
    coordinator = entry.runtime_data
    data = coordinator.data
    tariff = data.tariff
    return {
        "entry": {
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "older_history_imported": coordinator.history_imported,
        },
        "account": _mask(data.account_number),
        "meter": _mask(data.meter),
        "latest_hour": _jsonable(data.latest_hour),
        "latest_meter_read": data.latest_meter_read,
        "read_is_start_of_hour": data.read_is_start_of_hour,
        "daily": _jsonable(data.daily),
        "hourly_minimum": _jsonable(data.hourly_minimum),
        # Published rates, the same for every customer in the region.
        "tariff": _jsonable(tariff) if tariff is not None else None,
    }
