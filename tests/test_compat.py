"""The thameswaterapi shim tolerates new fields on meter lines."""

from __future__ import annotations

from dataclasses import MISSING, fields
from typing import Any

import pytest
import thameswaterapi

from custom_components.thames_water_meter import compat

# A meter line as Thames Water sends it from November 2026, with the new
# `continuousFlow` field that thameswaterapi 0.6.0 rejects.
LINE = {
    "Label": "00:00",
    "Usage": 1.5,
    "Read": 100.0,
    "IsEstimated": False,
    "MeterSerialNumberHis": "312330052",
    "continuousFlow": False,
}


def _payload(cls: type, lines: Any) -> dict[str, Any]:
    """A response body with every required field of `cls` filled in."""
    data: dict[str, Any] = {
        f.name: None for f in fields(cls) if f.default is MISSING and f.default_factory is MISSING
    }
    data["Lines"] = lines
    return data


@pytest.fixture(autouse=True)
def _installed() -> None:
    compat.install()


def test_unpatched_library_still_rejects_new_field() -> None:
    """Fails once thameswaterapi handles this itself; then drop compat.py."""
    original = thameswaterapi.parse_meter_usage.__wrapped__
    with pytest.raises(TypeError, match="continuousFlow"):
        original(_payload(thameswaterapi.MeterUsage, [LINE]))


def test_meters_response_with_unknown_line_field() -> None:
    result = thameswaterapi.parse_meters_response(_payload(thameswaterapi.MetersResponse, [LINE]))
    assert result.Lines[0].MeterSerialNumberHis == "312330052"
    assert not hasattr(result.Lines[0], "continuousFlow")


def test_meter_usage_with_unknown_line_field() -> None:
    result = thameswaterapi.parse_meter_usage(_payload(thameswaterapi.MeterUsage, [LINE]))
    assert result.Lines[0].Usage == 1.5


def test_null_lines_still_accepted() -> None:
    result = thameswaterapi.parse_meters_response(_payload(thameswaterapi.MetersResponse, None))
    assert result.Lines == []


def test_install_is_idempotent() -> None:
    first = thameswaterapi.parse_meter_usage
    compat.install()
    assert thameswaterapi.parse_meter_usage is first
