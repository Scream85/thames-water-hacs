"""Config flow for Thames Water Smart Meter."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import requests
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.selector import DateSelector
from thameswaterapi import (
    AuthenticationError,
    MalformedResponse,
    RateLimitError,
    ThamesWater,
)

from .const import (
    CONF_BILLING_PERIOD_END,
    CONF_BILLING_PERIOD_START,
    CONF_SPIKE_THRESHOLD,
    DEFAULT_SPIKE_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


def _login(email: str, password: str) -> tuple[int, list[str]]:
    """Blocking: authenticate and return (account, meters)."""
    client = ThamesWater(email=email, password=password)
    client.authenticate()
    meters = client.get_meters().Meters
    return client.account_number, meters


class ThamesWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _try(self, email: str, password: str):
        """Return (result, error)."""
        try:
            result = await self.hass.async_add_executor_job(_login, email, password)
        except AuthenticationError:
            return None, "invalid_auth"
        except (requests.RequestException, MalformedResponse, RateLimitError):
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during Thames Water login")
            return None, "unknown"
        if not result[1]:
            return None, "no_meter"
        return result, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            result, error = await self._try(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                account, _meters = result
                await self.async_set_unique_id(str(account))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Thames Water {account}",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            result, error = await self._try(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(str(result[0]))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> ThamesWaterOptionsFlow:
        return ThamesWaterOptionsFlow()


class ThamesWaterOptionsFlow(OptionsFlowWithReload):
    """Options: the daily spike threshold, and the dates of the current bill."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            start = user_input.get(CONF_BILLING_PERIOD_START)
            end = user_input.get(CONF_BILLING_PERIOD_END)
            # Dates arrive as ISO text, which sorts the same way as the dates do.
            if start and end and end < start:
                errors["base"] = "end_before_start"
            else:
                return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SPIKE_THRESHOLD, DEFAULT_SPIKE_THRESHOLD)
        schema = vol.Schema(
            {
                vol.Required(CONF_SPIKE_THRESHOLD, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Optional(CONF_BILLING_PERIOD_START): DateSelector(),
                vol.Optional(CONF_BILLING_PERIOD_END): DateSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or dict(self.config_entry.options)
            ),
            errors=errors,
        )
