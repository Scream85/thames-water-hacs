"""Fixtures for the Thames Water integration tests.

The two autouse fixtures follow the pattern in jelmer/homeassistant-thameswater
(Apache-2.0), tests/conftest.py: enable custom integrations, and stand in for the
recorder the manifest depends on.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Let Home Assistant load `custom_components` during a test."""
    yield


@pytest.fixture(autouse=True)
def mock_recorder_before_hass() -> Generator[None]:
    """Stand in for the recorder the manifest depends on.

    Setting a real one up needs a database prepared before `hass` exists.
    Statistics writes are asserted on `async_add_external_statistics` instead.
    """
    with patch("homeassistant.components.recorder.async_setup", return_value=True):
        yield
