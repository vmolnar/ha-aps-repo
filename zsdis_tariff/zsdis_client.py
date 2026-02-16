"""
ZSDIS client for fetching tariff data.
"""
import re
import logging
from datetime import datetime, timedelta

import requests

_LOGGER = logging.getLogger(__name__)


class ZsdisClient:
    """Client for fetching ZSDIS tariff data."""

    def __init__(self, hdo_code: int):
        """Initialize the ZSDIS client."""
        self.hdo_code = hdo_code
        self.base_url = "https://www.zsdis.sk/Uvod/Online-sluzby/Casy-prepinania-nizkej-a-vysokej-tarify"

    def split_intervals_at_midnight(self, intervals):
        """Split intervals that cross midnight into two separate intervals."""
        split_intervals = []
        
        for interval in intervals:
            start_time = datetime.strptime(interval['t_from'], "%H:%M").time()
            end_time = datetime.strptime(interval['t_to'], "%H:%M").time()
            
            # Check if interval crosses midnight
            if start_time > end_time:
                # Split into two intervals
                split_intervals.append({
                    't_from': interval['t_from'],
                    't_to': "23:59"
                })
                split_intervals.append({
                    't_from': "00:00",
                    't_to': interval['t_to']
                })
            else:
                split_intervals.append(interval)
        
        return split_intervals

    def validate_no_overlapping_intervals(self, intervals):
        """Validate that intervals don't overlap. Returns True if valid, False if overlaps found."""
        if not intervals:
            return True
            
        # Convert intervals to minutes for easier comparison
        interval_ranges = []
        for interval in intervals:
            start_time = datetime.strptime(interval['t_from'], "%H:%M")
            end_time = datetime.strptime(interval['t_to'], "%H:%M")
            
            # Handle midnight crossover
            if end_time < start_time:
                end_time = end_time + timedelta(days=1)
            
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            
            interval_ranges.append((start_minutes, end_minutes))
        
        # Sort intervals by start time
        interval_ranges.sort()
        
        # Check for overlaps
        for i in range(1, len(interval_ranges)):
            prev_start, prev_end = interval_ranges[i-1]
            curr_start, curr_end = interval_ranges[i]
            
            # Check if current interval starts before previous ends (with 24-hour wrap-around)
            if curr_start < prev_end:
                prev_start_hour = interval_ranges[i-1][0] // 60
                prev_start_min = interval_ranges[i-1][0] % 60
                prev_end_hour = interval_ranges[i-1][1] // 60
                prev_end_min = interval_ranges[i-1][1] % 60
                curr_start_hour = interval_ranges[i][0] // 60
                curr_start_min = interval_ranges[i][0] % 60
                curr_end_hour = interval_ranges[i][1] // 60
                curr_end_min = interval_ranges[i][1] % 60
                
                _LOGGER.warning("Overlapping intervals detected: %02d:%02d-%02d:%02d and %02d:%02d-%02d:%02d", 
                              prev_start_hour, prev_start_min, prev_end_hour, prev_end_min,
                              curr_start_hour, curr_start_min, curr_end_hour, curr_end_min)
                return False
        
        return True

    def calculate_high_tariff_intervals(self, low_intervals):
        """Calculate high tariff intervals from low tariff intervals."""
        if not low_intervals:
            # Edge case: No low tariff intervals means 24/7 high tariff
            _LOGGER.info("No low tariff intervals found - assuming 24/7 high tariff")
            return [{"t_from": "00:00", "t_to": "23:59"}]
        
        # Create a timeline of all minutes in a day
        timeline = [False] * (24 * 60)  # False = high tariff, True = low tariff
        
        # Mark low tariff periods on the timeline
        for interval in low_intervals:
            start_time = datetime.strptime(interval['t_from'], "%H:%M")
            end_time = datetime.strptime(interval['t_to'], "%H:%M")
            
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            
            # Handle midnight crossover
            if end_time < start_time:
                # Interval crosses midnight, mark in two parts
                # Part 1: from start to end of day (exclusive of end)
                for i in range(start_minutes, 24 * 60):
                    timeline[i] = True
                # Part 2: from start of day to end (exclusive of end)
                for i in range(0, end_minutes):
                    timeline[i] = True
            else:
                # Normal interval (exclusive of end)
                for i in range(start_minutes, end_minutes):
                    timeline[i % (24 * 60)] = True
        
        # Check if entire day is low tariff (24/7 low tariff scenario)
        # We need to check if the timeline is all True, but be careful about the last minute
        all_low = True
        for minute in range(24 * 60):
            if not timeline[minute]:
                all_low = False
                break
                
        if all_low:
            _LOGGER.info("Entire day is low tariff - no high tariff periods")
            return []
        
        # Debug: Check if we have a single minute gap at the end
        if len(low_intervals) == 1 and low_intervals[0]['t_from'] == "00:00" and low_intervals[0]['t_to'] == "23:59":
            # This should be all low tariff, but there might be a boundary issue
            _LOGGER.info("Detected 00:00-23:59 interval - treating as 24/7 low tariff")
            return []
        
        # Find high tariff intervals from the timeline
        high_intervals = []
        current_high_start = None
        
        for minute in range(24 * 60 + 1):  # Include one extra minute to catch the end boundary
            is_high_tariff = False
            if minute < 24 * 60:
                is_high_tariff = not timeline[minute]
            else:
                # Virtual minute at the end to catch the final interval
                is_high_tariff = False
            
            if is_high_tariff:  # High tariff
                if current_high_start is None:
                    current_high_start = minute
            else:  # Low tariff or end of day
                if current_high_start is not None:
                    # Convert minutes to HH:MM format
                    start_hour = current_high_start // 60
                    start_minute = current_high_start % 60
                    # The end of high tariff is the minute when low tariff starts (inclusive)
                    end_hour = minute // 60
                    end_minute = minute % 60
                    
                    # Handle the case where end time would be 24:00 (end of day)
                    if end_hour == 24:
                        end_hour = 23
                        end_minute = 59
                    
                    # Calculate duration in minutes
                    duration_minutes = (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
                    
                    # Only add interval if it has positive duration (at least 1 minute)
                    if duration_minutes >= 1:
                        high_intervals.append({
                            't_from': f"{start_hour:02d}:{start_minute:02d}",
                            't_to': f"{end_hour:02d}:{end_minute:02d}"
                        })
                    else:
                        _LOGGER.debug(f"Skipping zero-duration high tariff interval: {start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}")
                    current_high_start = None
        
        return high_intervals

    def fetch_tariff_data(self):
        """Fetch ZSDIS page and return tariff times for the configured HDO code."""
        try:
            _LOGGER.debug("Downloading data from ZSDIS website for HDO code %s...", self.hdo_code)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.base_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            html_content = response.text
            
            # Extract tariff data
            _LOGGER.debug("Processing data...")
            
            # Find the tariff with the specified code
            tariff_pattern = r'\{\s*code:\s*' + str(self.hdo_code) + r'\s*,\s*intervals:\s*\[(.*?)\]\s*\}'
            match = re.search(tariff_pattern, html_content, re.DOTALL)
            
            if not match:
                _LOGGER.error("HDO code %s not found.", self.hdo_code)
                return None
            
            intervals_str = match.group(1)
            
            # Parse intervals
            intervals = []
            interval_pattern = r'\{(.*?)\}'
            interval_matches = re.findall(interval_pattern, intervals_str, re.DOTALL)
            
            low_tariff_intervals = []
            
            for interval_match in interval_matches:
                interval = {}
                
                # Extract properties
                telegram_match = re.search(r'telegram:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['telegram'] = telegram_match.group(1) if telegram_match else ''
                
                t_type_match = re.search(r't_type:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['t_type'] = t_type_match.group(1) if t_type_match else ''
                
                t_from_match = re.search(r't_from:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['t_from'] = t_from_match.group(1) if t_from_match else ''
                
                t_to_match = re.search(r't_to:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['t_to'] = t_to_match.group(1) if t_to_match else ''
                
                weekday_match = re.search(r'weekday:\s*(true|false)', interval_match)
                interval['weekday'] = weekday_match.group(1) == 'true' if weekday_match else False
                
                weekend_match = re.search(r'weekend:\s*(true|false)', interval_match)
                interval['weekend'] = weekend_match.group(1) == 'true' if weekend_match else False
                
                meaning_match = re.search(r'meaning:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['meaning'] = meaning_match.group(1) if meaning_match else ''
                
                for_rate_match = re.search(r'for_rate:\s*[\"\'](.*?)[\"\']', interval_match)
                interval['for_rate'] = for_rate_match.group(1) if for_rate_match else ''
                
                # Only keep low tariff intervals (t_type = 'nt')
                if interval['t_type'] == 'nt':
                    low_tariff_intervals.append(interval)
            
            if not low_tariff_intervals:
                _LOGGER.error("No low tariff intervals found for HDO code %s.", self.hdo_code)
                return None
            
            # Group by day type
            weekday_intervals = [i for i in low_tariff_intervals if i['weekday'] and not i['weekend']]
            weekend_intervals = [i for i in low_tariff_intervals if i['weekend'] and not i['weekday']]
            all_week_intervals = [i for i in low_tariff_intervals if i['weekday'] and i['weekend']]
            
            # Split intervals that cross midnight
            all_week_intervals = self.split_intervals_at_midnight(all_week_intervals)
            weekday_intervals = self.split_intervals_at_midnight(weekday_intervals)
            weekend_intervals = self.split_intervals_at_midnight(weekend_intervals)
            
            # Validate no overlapping intervals after splitting
            self.validate_no_overlapping_intervals(all_week_intervals)
            self.validate_no_overlapping_intervals(weekday_intervals)
            self.validate_no_overlapping_intervals(weekend_intervals)
            
            # Calculate high tariff intervals from low tariff intervals
            high_all_week = self.calculate_high_tariff_intervals(all_week_intervals)
            
            # Only calculate day-specific high tariff intervals if there are day-specific low tariff intervals
            # If there are no day-specific low tariff intervals, day-specific high tariff should be empty
            # (the all_week intervals will apply to all days)
            if weekday_intervals:
                high_weekdays = self.calculate_high_tariff_intervals(weekday_intervals)
            else:
                high_weekdays = []
                
            if weekend_intervals:
                high_weekend = self.calculate_high_tariff_intervals(weekend_intervals)
            else:
                high_weekend = []
            
            # Build result with both low and high tariff times
            result = {
                "hdo_code": self.hdo_code,
                "low_tariff": {
                    "all_week": [{"from": i['t_from'], "to": i['t_to']} for i in all_week_intervals] if all_week_intervals else [],
                    "weekdays": [{"from": i['t_from'], "to": i['t_to']} for i in weekday_intervals] if weekday_intervals else [],
                    "weekend": [{"from": i['t_from'], "to": i['t_to']} for i in weekend_intervals] if weekend_intervals else []
                },
                "high_tariff": {
                    "all_week": [{"from": i['t_from'], "to": i['t_to']} for i in high_all_week] if high_all_week else [],
                    "weekdays": [{"from": i['t_from'], "to": i['t_to']} for i in high_weekdays] if high_weekdays else [],
                    "weekend": [{"from": i['t_from'], "to": i['t_to']} for i in high_weekend] if high_weekend else []
                }
            }
            
            return result
            
        except requests.RequestException as e:
            _LOGGER.error("Error downloading data: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("Error processing data: %s", e)
            return None