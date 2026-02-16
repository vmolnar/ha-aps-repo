"""
Config flow for ZSDIS Tariff integration.
"""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_HDO_CODE

_LOGGER = logging.getLogger(__name__)


class ZsdisTariffConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZSDIS Tariff."""

    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Create the config entry
            return self.async_create_entry(
                title=f"ZSDIS Tariff (HDO: {user_input['hdo_code']})",
                data=user_input,
            )
        
        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("hdo_code", default=DEFAULT_HDO_CODE): int,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ZsdisTariffOptionsFlow(config_entry)


class ZsdisTariffOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ZSDIS Tariff."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "hdo_code",
                        default=self.config_entry.options.get("hdo_code", DEFAULT_HDO_CODE),
                    ): int,
                }
            ),
        )