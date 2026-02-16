"""
Binary sensor platform for ZSDIS tariff times.
"""
import logging
from datetime import datetime, time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .zsdis_client import ZsdisClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZSDIS Tariff binary sensors."""
    _LOGGER.debug("Setting up ZSDIS Tariff binary sensors")
    
    # Get the coordinator from the sensor setup
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create binary sensor
    binary_sensor = ZsdisCurrentTariffBinarySensor(coordinator)
    
    async_add_entities([binary_sensor])
    
    # Set up time change listener for immediate updates
    await binary_sensor.async_setup_time_listener(hass)


class ZsdisCurrentTariffBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a ZSDIS Current Tariff binary sensor."""
    
    def __init__(self, coordinator):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_high_tariff"
        self._attr_name = "zsdis_high_tariff"
        self._attr_icon = "mdi:flash"
        self._attr_device_class = "power"
        self._unsubscribe_time_listener = None
    
    async def async_setup_time_listener(self, hass: HomeAssistant):
        """Set up listener for time changes to update state immediately."""
        @callback
        def _handle_time_change(now):
            """Handle time change events."""
            self.async_write_ha_state()
        
        # Update every minute to catch tariff changes
        self._unsubscribe_time_listener = async_track_time_change(
            hass, _handle_time_change, second=0
        )
    
    async def async_will_remove_from_hass(self):
        """Clean up when entity is removed."""
        if self._unsubscribe_time_listener:
            self._unsubscribe_time_listener()
        await super().async_will_remove_from_hass()
    
    @property
    def is_on(self) -> bool:
        """Return true if currently in high tariff period."""
        if self.coordinator.data is None:
            return None
            
        # Get current local time
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()  # Monday = 0, Sunday = 6
        
        # Determine if today is weekday or weekend
        is_weekend = current_weekday >= 5  # Saturday (5) or Sunday (6)
        
        # Get the appropriate tariff data
        data = self.coordinator.data.get('high_tariff', {})
        
        # Check intervals in order: all_week, then specific day type
        intervals_to_check = []
        
        # First check all_week intervals (applies to all days)
        intervals_to_check.extend(data.get('all_week', []))
        
        # Then check day-specific intervals
        if is_weekend:
            intervals_to_check.extend(data.get('weekend', []))
        else:
            intervals_to_check.extend(data.get('weekdays', []))
        
        # Check if current time is within any high tariff interval
        for interval in intervals_to_check:
            if self._is_time_in_interval(current_time, interval.get('from'), interval.get('to')):
                return True  # High tariff
        
        return False  # Low tariff
    
    def _is_time_in_interval(self, current_time: time, start_str: str, end_str: str) -> bool:
        """Check if current time is within the interval defined by start and end strings."""
        if not start_str or not end_str:
            return False
            
        try:
            # Parse time strings to time objects
            start_time = datetime.strptime(start_str, "%H:%M").time()
            
            # Handle special case for 24:00 (end of day)
            if end_str == "24:00":
                end_time = datetime.strptime("23:59", "%H:%M").time()
            else:
                end_time = datetime.strptime(end_str, "%H:%M").time()
            
            # Handle midnight crossover (e.g., 22:00 - 06:00)
            if start_time > end_time:
                # Interval crosses midnight
                if current_time >= start_time or current_time <= end_time:
                    return True
                else:
                    return False
            else:
                # Normal interval
                if start_time <= current_time <= end_time:
                    return True
                else:
                    return False
                    
        except (ValueError, TypeError) as e:
            _LOGGER.error("Error parsing time interval: %s", e)
            return False
    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
            
        # Get current time and determine day type
        now = datetime.now()
        current_weekday = now.weekday()
        is_weekend = current_weekday >= 5
        
        # Find current high tariff interval if any
        current_interval = None
        data = self.coordinator.data.get('high_tariff', {})
        
        # Check which interval we're currently in
        intervals_to_check = []
        intervals_to_check.extend(data.get('all_week', []))
        
        if is_weekend:
            intervals_to_check.extend(data.get('weekend', []))
        else:
            intervals_to_check.extend(data.get('weekdays', []))
        
        current_time = now.time()
        for interval in intervals_to_check:
            if self._is_time_in_interval(current_time, interval.get('from'), interval.get('to')):
                current_interval = interval
                break
        
        return {
            "hdo_code": self.coordinator.data.get("hdo_code"),
            "current_time": now.strftime("%H:%M"),
            "day_type": "weekend" if is_weekend else "weekday",
            "current_interval": current_interval,
            "last_updated": self.coordinator.data.get("last_updated"),
        }
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None and 'high_tariff' in self.coordinator.data