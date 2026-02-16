"""Config flow for Websupport DNS integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_DOMAIN,
    CONF_SUBDOMAINS,
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    CONF_TTL,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Websupport DNS."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        
        if user_input is not None:
            # Validate the configuration
            try:
                await self._validate_input(user_input)
            except CannotConnect:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_user_schema(),
                    errors={"base": "cannot_connect"},
                )
            except InvalidAuth:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_user_schema(),
                    errors={"base": "invalid_auth"},
                )
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_user_schema(),
                    errors={"base": "unknown"},
                )
            
            # Create the config entry
            return self.async_create_entry(
                title=user_input[CONF_DOMAIN],
                data={
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_API_SECRET: user_input[CONF_API_SECRET],
                    CONF_DOMAIN: user_input[CONF_DOMAIN],
                    CONF_SUBDOMAINS: user_input[CONF_SUBDOMAINS],
                    CONF_BASE_URL: user_input[CONF_BASE_URL],
                },
                options={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_TTL: user_input[CONF_TTL],
                },
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_user_schema(),
        )
    
    def _get_user_schema(self) -> vol.Schema:
        """Return the schema for the user input."""
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Required(CONF_DOMAIN): str,
                vol.Required(CONF_SUBDOMAINS, default=""): str,
                vol.Required(CONF_BASE_URL, default="rest.websupport.sk"): str,
                vol.Required(CONF_SCAN_INTERVAL, default=10): int,
                vol.Required(CONF_TTL, default=3600): int,
            }
        )
    
    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate the user input."""
        
        # Import here to avoid circular imports
        from .dns_manager import WebsupportDNSManager
        
        # Create DNS manager
        dns_manager = WebsupportDNSManager(
            user_input[CONF_API_KEY],
            user_input[CONF_API_SECRET],
            user_input[CONF_BASE_URL]
        )
        
        # Test authentication
        if not dns_manager.test_authentication():
            raise InvalidAuth
        
        # Test getting public IP
        try:
            ip_address = dns_manager.get_public_ip()
            _LOGGER.debug(f"Public IP validation successful: {ip_address}")
        except Exception as e:
            raise CannotConnect from e
        
        # Validate subdomains format
        subdomains = [s.strip() for s in user_input[CONF_SUBDOMAINS].split(",") if s.strip()]
        if not subdomains:
            raise InvalidSubdomains
        
        # Test getting service ID from domain (this will validate domain)
        try:
            service_id = dns_manager.get_service_id_from_domain(user_input[CONF_DOMAIN])
            _LOGGER.debug(f"Found service ID {service_id} for domain {user_input[CONF_DOMAIN]}")
        except Exception as e:
            _LOGGER.warning(f"Could not get service ID for domain: {str(e)}")
            # This is not a showstopper - domain might be valid but we can't resolve service ID yet


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidSubdomains(HomeAssistantError):
    """Error to indicate invalid subdomains."""


async def async_get_options_flow(config_entry):
    """Get the options flow for this handler."""
    return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Websupport DNS."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options flow."""
        
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 10)
                    ): int,
                    vol.Required(
                        CONF_TTL,
                        default=self.config_entry.options.get(CONF_TTL, 3600)
                    ): int,
                }
            ),
        )