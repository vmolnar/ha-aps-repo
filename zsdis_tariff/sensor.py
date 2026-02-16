"""
Sensor platform for ZSDIS tariff times.
"""
import logging
from datetime import timedelta, time

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, SENSOR_HIGH_TARIFF_PREFIX
from .zsdis_client import ZsdisClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZSDIS Tariff sensors."""
    _LOGGER.debug("Setting up ZSDIS Tariff sensors")
    
    # Get HDO code from config
    hdo_code = entry.data.get("hdo_code", 145)
    
    # Create the ZSDIS client
    client = ZsdisClient(hdo_code)
    
    # Create the update coordinator
    coordinator = ZsdisTariffDataUpdateCoordinator(hass, client)
    
    # Store coordinator for binary sensor platform to access
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Create sensors for each high tariff interval
    sensors = []
    
    if coordinator.data and 'high_tariff' in coordinator.data:
        high_tariff_data = coordinator.data['high_tariff']
        
        # Helper function to filter out tiny intervals (< 5 minutes)
        def filter_tiny_intervals(intervals):
            filtered = []
            for interval in intervals:
                try:
                    start_hour, start_min = map(int, interval['from'].split(':'))
                    end_hour, end_min = map(int, interval['to'].split(':'))
                    duration = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)
                    
                    # Only keep intervals that are at least 5 minutes long
                    if duration >= 5:
                        filtered.append(interval)
                    else:
                        _LOGGER.info(f"Filtering out tiny interval: {interval['from']}-{interval['to']} ({duration} minutes)")
                except (ValueError, KeyError, AttributeError) as e:
                    _LOGGER.warning(f"Error processing interval {interval}: {e}")
            return filtered
        
        # Helper function to check if day-type intervals are redundant
        def are_daytype_intervals_redundant(daytype_intervals, all_week_intervals):
            """Check if day-type intervals are redundant (same as 24/7 high tariff)."""
            # If there are no day-type intervals, they're not redundant
            if not daytype_intervals:
                return False
            
            # If there's more than one interval, they're not redundant
            if len(daytype_intervals) > 1:
                return False
            
            # Check if the single interval is 24/7 high tariff (00:00-23:59)
            single_interval = daytype_intervals[0]
            if single_interval.get('from') == '00:00' and single_interval.get('to') == '23:59':
                # This means 24/7 high tariff - check if all_week already covers everything
                # If all_week has intervals, then day-type is redundant
                return bool(all_week_intervals)
            
            return False
        
        # Get filtered intervals
        all_week_filtered = filter_tiny_intervals(high_tariff_data.get('all_week', []))
        weekdays_filtered = filter_tiny_intervals(high_tariff_data.get('weekdays', []))
        weekend_filtered = filter_tiny_intervals(high_tariff_data.get('weekend', []))
        
        # Check if day-type intervals are redundant
        weekdays_redundant = are_daytype_intervals_redundant(weekdays_filtered, all_week_filtered)
        weekend_redundant = are_daytype_intervals_redundant(weekend_filtered, all_week_filtered)
        
        if weekdays_redundant:
            _LOGGER.info("Skipping redundant weekday sensors (24/7 high tariff with all_week intervals present)")
        else:
            # Create sensors for weekdays intervals (filtered)
            for i, interval in enumerate(weekdays_filtered, 1):
                sensors.append(ZsdisHighTariffStartSensor(coordinator, i, 'weekdays'))
                sensors.append(ZsdisHighTariffEndSensor(coordinator, i, 'weekdays'))
        
        if weekend_redundant:
            _LOGGER.info("Skipping redundant weekend sensors (24/7 high tariff with all_week intervals present)")
        else:
            # Create sensors for weekend intervals (filtered)
            for i, interval in enumerate(weekend_filtered, 1):
                sensors.append(ZsdisHighTariffStartSensor(coordinator, i, 'weekend'))
                sensors.append(ZsdisHighTariffEndSensor(coordinator, i, 'weekend'))
        
        # Always create all_week sensors
        for i, interval in enumerate(all_week_filtered, 1):
            sensors.append(ZsdisHighTariffStartSensor(coordinator, i, 'all_week'))
            sensors.append(ZsdisHighTariffEndSensor(coordinator, i, 'all_week'))
    
    async_add_entities(sensors)


class ZsdisTariffDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ZSDIS tariff data."""

    def __init__(self, hass: HomeAssistant, client: ZsdisClient):
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self):
        """Fetch data from ZSDIS."""
        try:
            _LOGGER.debug("Updating ZSDIS tariff data")
            data = await self.hass.async_add_executor_job(self.client.fetch_tariff_data)
            if data is None:
                raise UpdateFailed("Failed to fetch tariff data from ZSDIS - check HDO code and network connection")
            return data
        except Exception as err:
            _LOGGER.error("Error updating ZSDIS tariff data: %s", err)
            raise UpdateFailed(f"Error updating ZSDIS tariff data: {err}") from err


class ZsdisHighTariffStartSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ZSDIS High Tariff start time sensor."""

    def __init__(self, coordinator: ZsdisTariffDataUpdateCoordinator, interval_number: int, day_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._interval_number = interval_number
        self._day_type = day_type
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_HIGH_TARIFF_PREFIX}{interval_number}_start_{day_type}"
        self._attr_name = f"{SENSOR_HIGH_TARIFF_PREFIX}{interval_number}_start_{day_type}"
        self._attr_icon = "mdi:clock-start"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
            
        # Get the appropriate data based on the current day type
        data = self.coordinator.data.get('high_tariff', {})
        intervals = data.get(self._day_type, [])
        
        # Check if we have enough intervals
        if len(intervals) >= self._interval_number:
            time_str = intervals[self._interval_number - 1].get('from')
            if time_str:
                try:
                    # Parse the time string and return as time object
                    hour, minute = map(int, time_str.split(':'))
                    return time(hour, minute)
                except (ValueError, AttributeError):
                    return None
            return None
        else:
            return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
            
        return {
            "hdo_code": self.coordinator.data.get("hdo_code"),
            "day_type": self._day_type,
            "interval_number": self._interval_number,
            "last_updated": self.coordinator.data.get("last_updated"),
        }


class ZsdisHighTariffEndSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ZSDIS High Tariff end time sensor."""

    def __init__(self, coordinator: ZsdisTariffDataUpdateCoordinator, interval_number: int, day_type: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._interval_number = interval_number
        self._day_type = day_type
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_HIGH_TARIFF_PREFIX}{interval_number}_end_{day_type}"
        self._attr_name = f"{SENSOR_HIGH_TARIFF_PREFIX}{interval_number}_end_{day_type}"
        self._attr_icon = "mdi:clock-end"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
            
        # Get the appropriate data based on the current day type
        data = self.coordinator.data.get('high_tariff', {})
        intervals = data.get(self._day_type, [])
        
        # Check if we have enough intervals
        if len(intervals) >= self._interval_number:
            time_str = intervals[self._interval_number - 1].get('to')
            if time_str:
                try:
                    # Parse the time string and return as time object
                    hour, minute = map(int, time_str.split(':'))
                    return time(hour, minute)
                except (ValueError, AttributeError):
                    return None
            return None
        else:
            return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
            
        return {
            "hdo_code": self.coordinator.data.get("hdo_code"),
            "day_type": self._day_type,
            "interval_number": self._interval_number,
            "last_updated": self.coordinator.data.get("last_updated"),
        }