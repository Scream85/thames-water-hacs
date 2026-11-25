"""Workarounds for gaps in thameswaterapi.

thameswaterapi 0.6.0 builds each meter line with ``Line(**line)``, so any new
field Thames Water adds to a line (``continuousFlow`` from November 2026) makes
every getMeters and usage call fail. The top-level objects already ignore
unknown fields; this does the same for the lines, dropping unknown keys before
the library's own parsers see them.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import fields
from typing import Any

import thameswaterapi

_LOGGER = logging.getLogger(__name__)
_PATCHED = "_thames_water_meter_patched"
_warned: set[str] = set()


def _clean_lines(data: Any) -> Any:
    if not isinstance(data, dict) or not isinstance(data.get("Lines"), list):
        return data
    known = {f.name for f in fields(thameswaterapi.Line)}
    lines = []
    for line in data["Lines"]:
        if isinstance(line, dict):
            unknown = line.keys() - known
            new = unknown - _warned
            if new:
                _warned.update(new)
                _LOGGER.debug("Ignoring new meter line fields: %s", ", ".join(sorted(new)))
            line = {k: v for k, v in line.items() if k in known}
        lines.append(line)
    return {**data, "Lines": lines}


def _wrap(parse: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def wrapper(data: Any) -> Any:
        return parse(_clean_lines(data))

    functools.update_wrapper(wrapper, parse)
    setattr(wrapper, _PATCHED, True)
    return wrapper


def install() -> None:
    """Patch the library's line parsers. Safe to call more than once."""
    for name in ("parse_meters_response", "parse_meter_usage"):
        parse = getattr(thameswaterapi, name, None)
        if parse is None or getattr(parse, _PATCHED, False):
            continue
        setattr(thameswaterapi, name, _wrap(parse))
