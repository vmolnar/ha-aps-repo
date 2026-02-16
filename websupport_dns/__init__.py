"""
Websupport DNS Integration for Home Assistant

This integration automatically updates DNS A records on Websupport.sk
when the public IP address changes.
"""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    PLATFORMS,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Websupport DNS from a config entry."""
    
    # Store the config entry data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Set up the update coordinator
    coordinator = WebsupportDNSCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Store the coordinator
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class WebsupportDNSCoordinator(DataUpdateCoordinator):
    """Class to manage Websupport DNS updates."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)),
        )
        self.entry = entry
        self.dns_manager = None
        
    async def async_config_entry_first_refresh(self):
        """Perform the first refresh."""
        await self.async_refresh()
    
    async def async_refresh(self):
        """Update DNS records if IP has changed."""
        _LOGGER.debug("Websupport DNS update coordinator refresh")
        
        # Import here to avoid circular imports
        from .dns_manager import WebsupportDNSManager
        
        # Initialize DNS manager if not already done
        if self.dns_manager is None:
            self.dns_manager = WebsupportDNSManager(
                self.entry.data["api_key"],
                self.entry.data["api_secret"],
                self.entry.data["base_url"]
            )
        
        try:
            # Get current public IP
            current_ip = self.dns_manager.get_public_ip()
            _LOGGER.info(f"Current public IP: {current_ip}")
            
            # Update DNS records for all configured subdomains
            domain = self.entry.data["domain"]
            subdomains = self.entry.data["subdomains"]
            results = self.dns_manager.update_dns_records_for_subdomains(
                domain,
                subdomains,
                self.entry.options.get("ttl", 3600)
            )
            
            # Log results
            for result in results:
                if result["success"]:
                    _LOGGER.info(f"Successfully updated DNS record for {result['subdomain']}")
                else:
                    _LOGGER.error(f"Failed to update DNS record for {result['subdomain']}: {result['error']}")
            
            return results
            
        except Exception as e:
            _LOGGER.error(f"Failed to update DNS records: {str(e)}")
            raise


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)