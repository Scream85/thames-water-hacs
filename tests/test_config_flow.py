"""Tests for the Thames Water config, reauth and options flows."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
import requests
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from thameswaterapi import AuthenticationError

from custom_components.thames_water_meter.const import (
    CONF_BILLING_PERIOD_END,
    CONF_BILLING_PERIOD_START,
    CONF_SPIKE_THRESHOLD,
    DOMAIN,
)

ACCOUNT = 12345678
CREDENTIALS = {"email": "someone@example.com", "password": "hunter2"}
LOGIN = "custom_components.thames_water_meter.config_flow._login"


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Keep a created or reloaded entry from logging in for real."""
    with (
        patch("custom_components.thames_water_meter.async_setup_entry", return_value=True),
        patch("custom_components.thames_water_meter.async_unload_entry", return_value=True),
    ):
        yield


def _entry(**kwargs) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(ACCOUNT),
        data=CREDENTIALS,
        **kwargs,
    )


async def test_user_flow_creates_an_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(LOGIN, return_value=(ACCOUNT, ["M1"])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == CREDENTIALS
    assert result["result"].unique_id == str(ACCOUNT)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (AuthenticationError("rejected"), "invalid_auth"),
        (requests.ConnectionError("reset"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_reports_a_failed_login(
    hass: HomeAssistant, error: Exception, reason: str
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(LOGIN, side_effect=error):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}


async def test_user_flow_rejects_an_account_without_a_meter(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(LOGIN, return_value=(ACCOUNT, [])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)

    assert result["errors"] == {"base": "no_meter"}


async def test_user_flow_aborts_for_an_account_already_configured(
    hass: HomeAssistant,
) -> None:
    _entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(LOGIN, return_value=(ACCOUNT, ["M1"])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_stores_the_new_password(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    with patch(LOGIN, return_value=(ACCOUNT, ["M1"])) as login:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )

    # The stored email is used; only the password is asked for again.
    login.assert_called_once_with(CREDENTIALS["email"], "new-password")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-password"
    assert entry.data["email"] == CREDENTIALS["email"]


async def test_reauth_refuses_credentials_for_another_account(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with patch(LOGIN, return_value=(ACCOUNT + 1, ["M1"])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "someone-elses"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data["password"] == CREDENTIALS["password"]


async def test_reauth_reports_a_wrong_password(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    with patch(LOGIN, side_effect=AuthenticationError("rejected")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "wrong"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == CREDENTIALS["password"]


async def test_options_flow_sets_the_spike_threshold(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SPIKE_THRESHOLD: 1500}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SPIKE_THRESHOLD] == 1500


async def _options_flow(hass: HomeAssistant, entry: MockConfigEntry):
    return await hass.config_entries.options.async_init(entry.entry_id)


async def test_options_flow_sets_the_billing_period(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SPIKE_THRESHOLD: 800,
            CONF_BILLING_PERIOD_START: "2026-09-29",
            CONF_BILLING_PERIOD_END: "2026-10-28",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_BILLING_PERIOD_START] == "2026-09-29"
    assert entry.options[CONF_BILLING_PERIOD_END] == "2026-10-28"


async def test_options_flow_leaves_the_period_off_when_the_dates_are_empty(
    hass: HomeAssistant,
) -> None:
    entry = _entry(options={CONF_BILLING_PERIOD_START: "2026-09-29"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SPIKE_THRESHOLD: 800}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_BILLING_PERIOD_START not in entry.options  # clearing the field switches it off


async def test_options_flow_rejects_an_end_before_the_start(hass: HomeAssistant) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SPIKE_THRESHOLD: 800,
            CONF_BILLING_PERIOD_START: "2026-10-28",
            CONF_BILLING_PERIOD_END: "2026-09-29",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "end_before_start"}
    assert CONF_BILLING_PERIOD_START not in entry.options


async def test_options_flow_offers_the_saved_dates_again(hass: HomeAssistant) -> None:
    entry = _entry(options={CONF_BILLING_PERIOD_START: "2026-09-29"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    result = await _options_flow(hass, entry)

    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_BILLING_PERIOD_START] == "2026-09-29"
