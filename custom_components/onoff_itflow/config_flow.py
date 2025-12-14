"""Config flow for the ITFlow integration."""

from __future__ import annotations

from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_ITFLOW_API_KEY,
    CONF_ITFLOW_CLIENT_ID,
    CONF_ITFLOW_SERVER,
    CONF_PUBLIC_URL,
    CONF_INTEGRATION_MODE,
    INTEGRATION_MODE_FULL,
    INTEGRATION_MODE_TICKETS_ONLY,
    INTEGRATION_MODE_MANUAL,
    CONF_MASTER_ACCOUNT_MODE,
    CONF_ALERT_ON_ERRORS,
    CONF_CREATE_STARTUP_TICKET,
    CONF_ALERT_ON_NEW_UPDATE,
    CONF_ALERT_ON_AUTOMATION_FAILURE,
    CONF_ALERT_ON_ERROR_LOGS,
    CONF_ALERT_ON_BACKUP_FAILURE,
    CONF_ALERT_ON_REPAIRS,
    CONF_MONITOR_DISK,
    CONF_DISK_THRESHOLD,
    CONF_MONITOR_MEMORY,
    CONF_MEMORY_THRESHOLD,
    CONF_MONITOR_CPU,
    CONF_CPU_THRESHOLD,
    CONF_MONITOR_IP,
    CONF_GATEWAY_IP,
    CONF_CF_TUNNEL_ENABLED,
    CONF_CF_TUNNEL_IP,
    DEFAULT_DISK_THRESHOLD,
    DEFAULT_MEMORY_THRESHOLD,
    DEFAULT_CPU_THRESHOLD,
    CONF_HEALTH_REPORT_ENABLED,
    CONF_HEALTH_REPORT_FREQUENCY,
    HEALTH_REPORT_DAILY,
    HEALTH_REPORT_WEEKLY,
    HEALTH_REPORT_MONTHLY,
    HEALTH_REPORT_NEVER,
    CONF_BACKUP_CHECK_ENABLED,
    CONF_BACKUP_CHECK_FREQUENCY,
    BACKUP_CHECK_DAILY,
    BACKUP_CHECK_WEEKLY,
    BACKUP_CHECK_MONTHLY,
    BACKUP_CHECK_NEVER,
)
from .itflow_api import ITFlowClient

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_INTEGRATION_MODE, default=INTEGRATION_MODE_FULL): vol.In([INTEGRATION_MODE_FULL, INTEGRATION_MODE_MANUAL]),
    }
)


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}
        self._clients = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_itflow()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors={}
        )

    async def async_step_itflow(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle ITFlow configuration step."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)

            # Check if manual mode - skip automation options
            if self._data.get(CONF_INTEGRATION_MODE) in [INTEGRATION_MODE_TICKETS_ONLY, INTEGRATION_MODE_MANUAL]:
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data
                )
            else:
                # Go to automation options
                return await self.async_step_automation_options()

        # Build schema (server URL is now hardcoded to ticket.onoffapi.com)
        schema = vol.Schema({
            vol.Required(CONF_ITFLOW_API_KEY): cv.string,
            vol.Required(CONF_ITFLOW_CLIENT_ID): cv.string,
            vol.Optional(CONF_PUBLIC_URL): cv.string,
        })

        return self.async_show_form(
            step_id="itflow",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors
        )


    async def async_step_automation_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle automation and alerting options."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_monitoring_options()

        return self.async_show_form(
            step_id="automation_options",
            data_schema=vol.Schema({
                vol.Optional(CONF_CREATE_STARTUP_TICKET, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_ERRORS, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_NEW_UPDATE, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_AUTOMATION_FAILURE, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_ERROR_LOGS, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_BACKUP_FAILURE, default=False): cv.boolean,
                vol.Optional(CONF_ALERT_ON_REPAIRS, default=False): cv.boolean,
                vol.Optional(CONF_HEALTH_REPORT_ENABLED, default=False): cv.boolean,
                vol.Optional(CONF_HEALTH_REPORT_FREQUENCY, default=HEALTH_REPORT_WEEKLY): vol.In([HEALTH_REPORT_DAILY, HEALTH_REPORT_WEEKLY, HEALTH_REPORT_MONTHLY, HEALTH_REPORT_NEVER]),
                vol.Optional(CONF_BACKUP_CHECK_ENABLED, default=False): cv.boolean,
                vol.Optional(CONF_BACKUP_CHECK_FREQUENCY, default=BACKUP_CHECK_WEEKLY): vol.In([BACKUP_CHECK_DAILY, BACKUP_CHECK_WEEKLY, BACKUP_CHECK_MONTHLY, BACKUP_CHECK_NEVER]),
            }),
            errors=errors
        )

    async def async_step_monitoring_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle system monitoring options."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data[CONF_NAME], data=self._data
            )

        return self.async_show_form(
            step_id="monitoring_options",
            data_schema=vol.Schema({
                vol.Optional("enable_system_sensors", default=True): cv.boolean,
                vol.Optional(CONF_MONITOR_DISK, default=True): cv.boolean,
                vol.Optional(CONF_DISK_THRESHOLD, default=DEFAULT_DISK_THRESHOLD): vol.All(vol.Coerce(int), vol.Range(min=50, max=99)),
                vol.Optional(CONF_MONITOR_MEMORY, default=True): cv.boolean,
                vol.Optional(CONF_MEMORY_THRESHOLD, default=DEFAULT_MEMORY_THRESHOLD): vol.All(vol.Coerce(int), vol.Range(min=50, max=99)),
                vol.Optional(CONF_MONITOR_CPU, default=True): cv.boolean,
                vol.Optional(CONF_CPU_THRESHOLD, default=DEFAULT_CPU_THRESHOLD): vol.All(vol.Coerce(int), vol.Range(min=50, max=99)),
                vol.Optional(CONF_MONITOR_IP, default=True): cv.boolean,
                vol.Optional("enable_ping_sensors", default=True): cv.boolean,
                vol.Optional(CONF_GATEWAY_IP): cv.string,
                vol.Optional(CONF_CF_TUNNEL_ENABLED, default=False): cv.boolean,
                vol.Optional(CONF_CF_TUNNEL_IP): cv.string,
            }),
            errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="reconfigure_failed")

        if user_input is not None:
            # Update the entry with new data
            return self.async_update_reload_and_abort(
                entry,
                data={**entry.data, **user_input},
            )

        # Prepare schema with current values
        current_data = entry.data

        # Build schema (server URL is now hardcoded)
        schema = vol.Schema({
            vol.Required(CONF_NAME, default=current_data.get(CONF_NAME)): cv.string,
            vol.Required(CONF_ITFLOW_API_KEY, default=current_data.get(CONF_ITFLOW_API_KEY, "")): cv.string,
            vol.Required(CONF_ITFLOW_CLIENT_ID, default=current_data.get(CONF_ITFLOW_CLIENT_ID, "")): cv.string,
            vol.Optional(CONF_PUBLIC_URL, default=current_data.get(CONF_PUBLIC_URL, "")): cv.string,
        })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle options flow for OnOff Automations integration."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # No options currently available
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
