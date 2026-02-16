"""
Custom integration for ZSDIS tariff times.
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ZSDIS Tariff component."""
    _LOGGER.debug("Setting up ZSDIS Tariff component")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ZSDIS Tariff from a config entry."""
    _LOGGER.debug("Setting up ZSDIS Tariff config entry: %s", entry.title)

    # Forward the setup to the sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug("Unloading ZSDIS Tariff config entry: %s", entry.title)
    
    # Unload the sensor platform
    sensor_unload = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    
    # Unload the binary_sensor platform
    binary_sensor_unload = await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    
    # Return True only if both platforms unloaded successfully
    return sensor_unload and binary_sensor_unload