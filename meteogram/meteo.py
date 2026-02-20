#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import math
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
import zoneinfo
import time
import logging
import gc
# Use default/interactive backend so the meteogram can be shown directly
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import numpy as np
import locale
from matplotlib.font_manager import FontProperties

# Global icon cache to avoid repeated disk reads
_icon_cache = {}

class Meteo:
    
    def __init__(self, location_name="Bratislava, Slovakia", latitude=48.1486, longitude=17.1077, 
                 timezone="Europe/Bratislava", model="icon_seamless", output_file="meteogram.png"):
        """
        Initialize Meteo instance with location and configuration.
        
        Args:
            location_name: Display name for the location
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            timezone: IANA timezone name
            model: Weather model (default: icon_seamless for DWD ICON-EU)
            output_file: Output PNG filename
        """
        self.location_name = location_name
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.model = model
        self.output_file = output_file
        
        # Configure logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def init():
        """
        Initialize locale and matplotlib settings for meteogram generation.
        """
        # Ensure English weekday/month names regardless of system locale
        # Try to set C locale (English) for time; fall back to en_US.UTF-8 if available.
        try:
            locale.setlocale(locale.LC_TIME, "C")
        except Exception:
            try:
                locale.setlocale(locale.LC_TIME, "en_US.UTF-8")
            except Exception:
                pass
        
        # Configure matplotlib date formatting
        matplotlib.rcParams["date.converter"] = "auto"
        matplotlib.rcParams["date.autoformatter.day"] = "%a %d"
        matplotlib.rcParams["date.autoformatter.hour"] = "%H"

    def fetch_open_meteo(self, lat, lon, tz_name, model):
        """
        Fetch hourly and daily data from Open-Meteo API.
        Data is requested in GMT and will be converted to local time in the script.
        Time frame: current day from midnight + 4 full next days (5 days total).
        """
        base = "https://api.open-meteo.com/v1/forecast"
        # Determine time window in local time: midnight today to midnight of day+5
        tz = zoneinfo.ZoneInfo(tz_name)
        utc = zoneinfo.ZoneInfo("UTC")
        now_local = datetime.now(tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=5)  # Exclusive end: midnight of 6th day
        
        # Convert to UTC for API request with 1-day buffer on each side to ensure full coverage
        start_utc = start_local.astimezone(utc)
        end_utc = end_local.astimezone(utc)
        start_date = (start_utc - timedelta(days=1)).date()
        end_date = (end_utc + timedelta(days=1)).date()
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": ",".join([
                "temperature_2m",
                "precipitation",
                "precipitation_probability",
                "cloud_cover_low",
                "cloud_cover_mid",
                "cloud_cover_high",
                "wind_speed_10m",
                "wind_gusts_10m",
                "wind_direction_10m",
                "weather_code",
            ]),
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
            ]),
            # Correct parameter name is 'models'
            "models": model,
            "timezone": "GMT",  # Request data in GMT
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "wind_speed_unit": "kmh",
            # Do not include forecast_days when specifying start/end_date
        }
        url = base + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        # Basic validation to surface API-side errors
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"Open-Meteo error: {data.get('reason', data['error'])}")
        return data

    def parse_times(self, tstr_list, tz_name):
        """
        Parse ISO8601 strings from Open-Meteo (received in GMT) and convert to local timezone.
        Naive timestamps are treated as UTC/GMT, then converted to the target local timezone.
        """
        utc = zoneinfo.ZoneInfo("UTC")
        local_tz = zoneinfo.ZoneInfo(tz_name)
        out = []
        for s in tstr_list:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # Interpret as UTC (since we requested GMT from API)
                dt = dt.replace(tzinfo=utc)
            else:
                # Already has timezone info, convert to local
                dt = dt.astimezone(local_tz)
                continue
            # Convert UTC to local timezone
            dt = dt.astimezone(local_tz)
            out.append(dt)
        return out

    @staticmethod
    def wmo_icon(code):
        """
        Map WMO weather codes to a generic textual fallback symbol.
        This is used only if image icons are not found.
        Covers all standard WMO codes 0-99.
        """
        SUN = "☀"
        CLOUD = "☁"
        RAIN = "R"
        SNOW = "S"
        THUNDER = "T"
        FOG = "F"
        
        # Clear sky
        if code == 0:
            return SUN
        # Partly cloudy
        if code in (1, 2):
            return f"{SUN}{CLOUD}"
        # Overcast
        if code == 3:
            return CLOUD
        # Fog
        if code in (45, 48):
            return FOG
        # Drizzle: light, moderate, dense
        if code in (51, 53, 55):
            return f"{CLOUD}+{RAIN}"
        # Freezing drizzle
        if code in (56, 57):
            return f"{CLOUD}+{RAIN}"
        # Rain: slight, moderate, heavy
        if code in (61, 63, 65):
            return f"{CLOUD}+{RAIN}"
        # Freezing rain
        if code in (66, 67):
            return f"{CLOUD}+{RAIN}"
        # Snow: slight, moderate, heavy
        if code in (71, 73, 75):
            return f"{CLOUD}+{SNOW}"
        # Snow grains
        if code == 77:
            return f"{CLOUD}+{SNOW}"
        # Rain showers: slight, moderate, violent
        if code in (80, 81, 82):
            return f"{CLOUD}+{RAIN}"
        # Snow showers: slight, heavy
        if code in (85, 86):
            return f"{CLOUD}+{SNOW}"
        # Thunderstorm: slight/moderate, with hail
        if code in (95, 96, 99):
            return THUNDER
        return "•"

    @staticmethod
    def wmo_icon_image_path(code):
        """
        Map WMO weather codes to a local PNG icon file path.
        Place icons in ./icons/*.png
        Icons needed: sun.png, cloud.png, partly-cloudy.png, rain.png, 
                    heavy-rain.png, snow.png, fog.png, thunder.png, drizzle.png
        Covers all standard WMO codes 0-99.
        """
        base = "icons"
        
        # 0: Clear sky
        if code == 0:
            return f"{base}/sun.png"
        # 1-2: Partly cloudy
        if code in (1, 2):
            return f"{base}/partly-cloudy.png"
        # 3: Overcast
        if code == 3:
            return f"{base}/cloud.png"
        # 45, 48: Fog
        if code in (45, 48):
            return f"{base}/fog.png"
        # 51, 53, 55: Drizzle
        if code in (51, 53, 55):
            return f"{base}/drizzle.png"
        # 56, 57: Freezing drizzle
        if code in (56, 57):
            return f"{base}/drizzle.png"
        # 61, 63: Rain (slight, moderate)
        if code in (61, 63):
            return f"{base}/rain.png"
        # 65: Heavy rain
        if code == 65:
            return f"{base}/heavy-rain.png"
        # 66, 67: Freezing rain
        if code in (66, 67):
            return f"{base}/rain.png"
        # 71, 73, 75: Snow
        if code in (71, 73, 75):
            return f"{base}/snow.png"
        # 77: Snow grains
        if code == 77:
            return f"{base}/snow.png"
        # 80, 81: Rain showers
        if code in (80, 81):
            return f"{base}/rain.png"
        # 82: Violent rain showers
        if code == 82:
            return f"{base}/heavy-rain.png"
        # 85, 86: Snow showers
        if code in (85, 86):
            return f"{base}/snow.png"
        # 95, 96, 99: Thunderstorm
        if code in (95, 96, 99):
            return f"{base}/thunder.png"
        
        logging.debug(f"Unknown weather code: {code}")
        return f"{base}/unknown.png"

    @staticmethod
    def draw_icon_image(ax, when, y, path, zoom=0.06):
        """
        Draw an image icon centered at (when, y). 'path' points to a PNG.
        'zoom' controls size (0.06 is a reasonable small icon).
        Uses global cache to avoid repeated disk reads.
        """
        global _icon_cache
        try:
            if path not in _icon_cache:
                _icon_cache[path] = mpimg.imread(path)
            img = _icon_cache[path]
            oi = OffsetImage(img, zoom=zoom, resample=True)
            ab = AnnotationBbox(oi, (mdates.date2num(when), y), frameon=False, box_alignment=(0.5, 0.0), xybox=(0, 6), xycoords=('data', 'data'), boxcoords=("offset points", "offset points"))
            ax.add_artist(ab)
            return True
        except Exception:
            return False

    @staticmethod
    def temp_to_color(val_c):
        """
        Map temperature (C) to color across two gradients:
        below 0: light blue to purple (-30 to 0)
        above 0: light green to red (0 to 40)
        """
        # Return rgb tuple
        if val_c <= 0:
            # -30 -> light blue (#9dd6ff), 0 -> purple (#7e3ff2) as description says "light blue to purple (-30 c)"
            t = max(0.0, min(1.0, (val_c - (-30.0)) / (0.0 - (-30.0))))
            # interpolate between light blue (157,214,255) and purple (126,63,242)
            c1 = np.array([157, 214, 255]) / 255.0
            c2 = np.array([126, 63, 242]) / 255.0
            c = c1 * (1 - t) + c2 * t
        else:
            # 0 -> light green (#a8e6a3), 20 -> yellow (#ffe66b), 40 -> red (#ff3b30)
            if val_c <= 20:
                t = max(0.0, min(1.0, (val_c - 0.0) / 20.0))
                c1 = np.array([168, 230, 163]) / 255.0
                c2 = np.array([255, 230, 107]) / 255.0
                c = c1 * (1 - t) + c2 * t
            else:
                t = max(0.0, min(1.0, (val_c - 20.0) / 20.0))
                c1 = np.array([255, 230, 107]) / 255.0
                c2 = np.array([255, 59, 48]) / 255.0
                c = c1 * (1 - t) + c2 * t
        return tuple(c.tolist())

    def create_temp_gradient(self, ax, times, temps_c):
        """
        Create a vertical color gradient fill under temperature curve
        depending on value itself by segment-wise colored polygons.
        """
        # Build segments between each pair of points colored by average temperature
        x = mdates.date2num(times)
        y = np.array(temps_c, dtype=float)
        ax.plot(times, y, color="black", linewidth=1.2, zorder=3)
        # Fill to zero baseline to create area (in data coordinates)
        for i in range(len(x) - 1):
            xa, xb = x[i], x[i+1]
            ya, yb = y[i], y[i+1]
            avg = 0.5 * (ya + yb)
            color = Meteo.temp_to_color(avg)
            ax.fill_between(
                [mdates.num2date(xa), mdates.num2date(xb)],
                [ya, yb],
                [0, 0],
                color=color, alpha=0.8, linewidth=0.0, zorder=2
            )

    @staticmethod
    def nice_wind_arrow(ax, x, y, deg, color="#6a0dad"):
        """
        Draw an arrow pointing to direction the wind is blowing TO.
        deg is meteorological direction (0=N, 90=E).
        """
        rad = math.radians(deg)
        dx = math.sin(rad)
        dy = math.cos(rad)
        scale = 0.18
        ax.arrow(x, y, dx * scale, dy * scale, width=0.0, head_width=0.12, head_length=0.12, length_includes_head=True, color=color, alpha=0.9, zorder=4)

    @staticmethod
    def quantize_dir_8(deg):
        """
        Quantize meteorological wind direction (degrees) into 8 sectors and return unit vector (dx, dy).
        Sectors: N(0), NE(45), E(90), SE(135), S(180), SW(225), W(270), NW(315)
        """
        # Normalize
        d = deg % 360.0
        # Each sector is 45 degrees, centered on the compass points
        sector = int(((d + 22.5) % 360) // 45)  # 0..7
        angle = math.radians(sector * 45.0)
        # Meteorological: 0=N (up), 90=E (right)
        dx = math.sin(angle)
        dy = math.cos(angle)
        return dx, dy, sector

    @staticmethod
    def ascii_arrow_for_sector(sector):
        """
        Return a readable Unicode arrow for a given 8-way sector (0..7).
        Mapping: 0=N(↑), 1=NE(↗), 2=E(→), 3=SE(↘), 4=S(↓), 5=SW(↙), 6=W(←), 7=NW(↖)
        """
        mapping = {
            0: "↑",  # N
            1: "↗",  # NE
            2: "→",  # E
            3: "↘",  # SE
            4: "↓",  # S
            5: "↙",  # SW
            6: "←",  # W
            7: "↖",  # NW
        }
        return mapping.get(sector, "•")

    @staticmethod
    def draw_wind_arrow_simple(ax, x, y, dx, dy, color="#4d238a", shaft_len=0.12, head_len=0.06, head_width=0.05):
        """
        Draw a simple arrow with a thin shaft and small triangular head.
        x, y are in data coords (x as date num, y in axis units on wind plot).
        dx, dy is a unit direction vector pointing TO where wind blows.
        shaft_len, head_len are in x/y mixed scales: x in date units, y scaled similar via axes transform for visibility.
        """
        # Shaft end
        x2 = x + dx * shaft_len
        y2 = y + dy * 0.0  # keep y constant for clarity (arrow placed in top band)
        # Draw shaft
        ax.plot([x, x2], [y, y2], color=color, linewidth=1.1, zorder=5)
        # Compute head triangle at the end
        # Perpendicular vector for width (screen-space approx using dy,-dx)
        perp_dx = -dy
        perp_dy = dx
        hx_base = x2 - dx * head_len
        hy_base = y2 - dy * 0.0
        left_x = hx_base + perp_dx * head_width
        left_y = hy_base + perp_dy * head_width
        right_x = hx_base - perp_dx * head_width
        right_y = hy_base - perp_dy * head_width
        head = plt.Polygon([[x2, y2], [left_x, left_y], [right_x, right_y]], closed=True, facecolor=color, edgecolor=color, linewidth=0.8, zorder=6)
        ax.add_patch(head)

    @staticmethod
    def setup_time_axes(fig, axes, times, tz_name):
        """
        Configure shared x-axis: daily major ticks with vlines; minor 6h ticks.
        Labels content:
        - Top chart (axes[0]) above: full weekday name + date YYYY-MM-DD
        - All charts below: majors = weekday abbreviation only; minors = HH (6-hourly)
        """
        tz = zoneinfo.ZoneInfo(tz_name)

        # Determine visible range in local tz
        start_vis = times[0].astimezone(tz)
        end_vis = times[-1].astimezone(tz)

        # Compute day boundaries covering the visible range
        day_start = start_vis.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = (end_vis.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))

        majors = []
        t = day_start
        while t <= day_end:
            majors.append(t)
            t += timedelta(days=1)

        minors = []
        t = day_start
        while t <= day_end:
            minors.append(t)
            t += timedelta(hours=6)

        # English weekday names
        eng_weekdays_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        eng_weekdays_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for idx, ax in enumerate(axes):
            ax.set_xlim(start_vis, end_vis)
            ax.xaxis.set_major_locator(mdates.HourLocator(byhour=0, tz=tz))
            ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 12, 18], tz=tz))
            ax.grid(False)

            # Major and minor vertical lines
            for mt in majors:
                ax.axvline(mt, color="#CCCCCC", linewidth=1.0, zorder=0)
            for mi in minors:
                ax.axvline(mi, color="#E6E6E6", linewidth=0.6, zorder=0, linestyle="-")

            # Formatters differ: top axis top labels show full weekday + date; bottom labels show abbr; minors show hour
            def major_fmt_abbr(x, pos=None, tz=tz):
                dt = mdates.num2date(x, tz=tz)
                return eng_weekdays_abbr[dt.weekday()]

            def major_fmt_full_with_date(x, pos=None, tz=tz):
                dt = mdates.num2date(x, tz=tz)
                return f"{eng_weekdays_full[dt.weekday()]} {dt.strftime('%Y-%m-%d')}"

            minor_fmt = mdates.DateFormatter("%H", tz=tz)

            # Apply formatters
            ax.xaxis.set_minor_formatter(minor_fmt)
            if idx == 0:
                # Top chart: top labels = full + date, bottom labels = abbrev
                ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(major_fmt_abbr))
                # We'll set visibility/padding later outside this function
            else:
                # Other charts: only need abbrev on bottom (we control visibility later)
                ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(major_fmt_abbr))

            # Use identical padding so major and minor tick labels sit on the same vertical level
            ax.tick_params(axis='x', which='major', pad=6, labelsize=11)
            ax.tick_params(axis='x', which='minor', pad=6, labelsize=10)

        # Alternating day background
        for i in range(len(majors) - 1):
            d0 = majors[i]
            d1 = majors[i + 1]
            if i % 2 == 1:
                for ax in axes:
                    ax.axvspan(d0, d1, color="#000000", alpha=0.03, zorder=0)

        # NOW line in local tz
        now_local = datetime.now(tz)
        for ax in axes:
            if start_vis <= now_local <= end_vis:
                ax.axvline(now_local, color="#ff0000", linewidth=1.2, zorder=5, linestyle="--")

        # Return formatters for external use (top full formatter)
        return matplotlib.ticker.FuncFormatter(major_fmt_full_with_date), matplotlib.ticker.FuncFormatter(major_fmt_abbr), minor_fmt

    @staticmethod
    def annotate_daily_minmax(ax, times, temps, daily_min_times, daily_mins, daily_max_times, daily_maxs):
        ax.scatter(daily_min_times, daily_mins, color="#0066cc", s=22, zorder=4)
        ax.scatter(daily_max_times, daily_maxs, color="#cc0000", s=22, zorder=4)
        # Keep labels inside axes and separated from points
        ymin, ymax = ax.get_ylim()
        xmin, xmax = ax.get_xlim()
        pad_y = 0.8
        pad_x_frac = 0.01  # 1% of time span
        time_span = xmax - xmin
        dx_inset = pad_x_frac * time_span

        # Helper to clamp x within limits with small inset
        def clamp_x(xval):
            return max(xmin + dx_inset, min(xmax - dx_inset, xval))

        # Min labels: place below point with extra offset; nudge inward if near edges
        for t, v in zip(daily_min_times, daily_mins):
            x = mdates.date2num(t)
            x = clamp_x(x)
            y = max(ymin + pad_y, min(ymax - pad_y, v - 1.0))
            # If too close to the point, push a bit more down
            va = "top"
            ax.text(mdates.num2date(x), y, f"{int(round(v))}°", color="#004a99",
                    ha="center", va=va, fontsize=14, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.6))

        # Max labels: place above point with extra offset; nudge inward if near edges
        for t, v in zip(daily_max_times, daily_maxs):
            x = mdates.date2num(t)
            x = clamp_x(x)
            y = max(ymin + pad_y, min(ymax - pad_y, v + 1.0))
            va = "bottom"
            ax.text(mdates.num2date(x), y, f"{int(round(v))}°", color="#990000",
                    ha="center", va=va, fontsize=14, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.6))

    @staticmethod
    def draw_cloud_background(ax, times, low, midc, high):
        """
        Draw three horizontal bands, opacity proportional to cloud cover percentage.
        Lower third: low, middle: mid, upper: high. Gray is #A0A0A0.
        """
        x0 = times[0]
        x1 = times[-1]
        # Determine y-range
        ylim = ax.get_ylim()
        y0, y1 = ylim
        # thirds
        y_low_top = y0 + (y1 - y0) / 3.0
        y_mid_top = y0 + 2.0 * (y1 - y0) / 3.0
        gray = (160/255.0, 160/255.0, 160/255.0)
        # Use step-wise alpha spans between time points
        for i in range(len(times)-1):
            a_low = max(0.0, min(1.0, low[i] / 100.0))
            a_mid = max(0.0, min(1.0, midc[i] / 100.0))
            a_high = max(0.0, min(1.0, high[i] / 100.0))
            ax.axvspan(times[i], times[i+1], ymin=0.0, ymax=(y_low_top - y0)/(y1 - y0), color=gray, alpha=a_low*0.8, zorder=0)
            ax.axvspan(times[i], times[i+1], ymin=(y_low_top - y0)/(y1 - y0), ymax=(y_mid_top - y0)/(y1 - y0), color=gray, alpha=a_mid*0.8, zorder=0)
            ax.axvspan(times[i], times[i+1], ymin=(y_mid_top - y0)/(y1 - y0), ymax=1.0, color=gray, alpha=a_high*0.8, zorder=0)

    def build_figure(self, data):
        tzname = self.timezone  # Use configured timezone, not API returned (which is GMT)
        hourly = data["hourly"]
        daily = data["daily"]

        # Parse all times and convert to local timezone
        times_all = self.parse_times(hourly["time"], tzname)
        
        # Filter to exact 5-day window: current day midnight to midnight of day+5
        tz = zoneinfo.ZoneInfo(tzname)
        now_local = datetime.now(tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=5)
        
        # Find indices within the desired local time range
        indices = [i for i, t in enumerate(times_all) if start_local <= t < end_local]
        
        # Slice all hourly data to the filtered indices
        times = [times_all[i] for i in indices]
        temp = [hourly["temperature_2m"][i] for i in indices]
        precip = [hourly["precipitation"][i] for i in indices]
        precip_prob = [hourly.get("precipitation_probability", [0]*len(times_all))[i] for i in indices]
        cloud_low = [hourly.get("cloud_cover_low", [0]*len(times_all))[i] for i in indices]
        cloud_mid = [hourly.get("cloud_cover_mid", [0]*len(times_all))[i] for i in indices]
        cloud_high = [hourly.get("cloud_cover_high", [0]*len(times_all))[i] for i in indices]
        wind_speed = [hourly.get("wind_speed_10m", [0]*len(times_all))[i] for i in indices]
        wind_gust = [hourly.get("wind_gusts_10m", [0]*len(times_all))[i] for i in indices]
        wind_dir = [hourly.get("wind_direction_10m", [0]*len(times_all))[i] for i in indices]
        wcode = [hourly.get("weather_code", [0]*len(times_all))[i] for i in indices]

        # Prepare daily min/max times by locating nearest hour to daily min/max value within each day
        # Parse all daily data and convert to local time
        daily_dates_all = self.parse_times(daily["time"], tzname)
        tmin_all = daily["temperature_2m_min"]
        tmax_all = daily["temperature_2m_max"]
        
        # Filter daily data to our 5-day window
        # Daily dates represent the start of each day; include if within our range
        daily_indices = [i for i, d in enumerate(daily_dates_all) if start_local <= d < end_local]
        daily_dates = [daily_dates_all[i] for i in daily_indices]
        tmin = [tmin_all[i] for i in daily_indices]
        tmax = [tmax_all[i] for i in daily_indices]
        
        daily_min_times = []
        daily_max_times = []
        for d, vmin, vmax in zip(daily_dates, tmin, tmax):
            # Find indices in filtered hourly data that share the same local date
            indices = [i for i, tt in enumerate(times) if tt.date() == d.date()]
            if indices:
                # Nearest index to min/max value among that day
                di = min(indices, key=lambda i: abs(temp[i] - vmin))
                ai = min(indices, key=lambda i: abs(temp[i] - vmax))
                daily_min_times.append(times[di])
                daily_max_times.append(times[ai])

        # Build figure
        fig = plt.figure(figsize=(14, 8), constrained_layout=False)
        # Add vertical spacing between charts to make room for x-axis labels
        gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 1.5, 1.5], hspace=0.18)
        ax_temp = fig.add_subplot(gs[0, 0])
        ax_prec = fig.add_subplot(gs[1, 0], sharex=ax_temp)
        ax_wind = fig.add_subplot(gs[2, 0], sharex=ax_temp)

        # Align neighboring subplot x-axes tightly
        for ax in (ax_temp, ax_prec, ax_wind):
            ax.margins(x=0)

        # Temperature chart
        self.create_temp_gradient(ax_temp, times, temp)
        # Weather icons every 6 hours: try image icons from ./icons, fallback to text symbol
        for i, (t, code) in enumerate(zip(times, wcode)):
            if t.hour % 6 == 0 and t.minute == 0:
                y = temp[i]
                icon_path = Meteo.wmo_icon_image_path(code)
                ok = Meteo.draw_icon_image(ax_temp, t, y + 1.2, icon_path, zoom=0.03)
                if not ok:
                    ax_temp.text(
                        t, y + 1.2, Meteo.wmo_icon(code),
                        ha="center", va="bottom", fontsize=11, zorder=6
                    )
        # Daily min/max annotations (daily_dates, tmin, tmax are already filtered to 5-day window)
        Meteo.annotate_daily_minmax(ax_temp, times, temp, daily_min_times, tmin[:len(daily_min_times)], daily_max_times, tmax[:len(daily_max_times)])
        ax_temp.set_ylabel("°C", fontsize=12)
        # Add slight vertical padding so the filled area and labels don't hug the borders
        ax_temp.margins(y=0.1)
        ax_temp.tick_params(axis='y', labelsize=11)
        ax_temp.grid(True, axis='y', color='#E0E0E0', linewidth=0.5, linestyle='-', alpha=0.7, zorder=10)

        # Precipitation chart with dual Y-axes
        # Left axis: precipitation (mm) and probability (% scaled visually as area)
        ax_prec_left = ax_prec
        # Right axis: cloud cover (%)
        ax_prec_right = ax_prec_left.twinx()
        # Ensure right axis artists don't cover left-axis bars
        ax_prec_right.set_zorder(0)
        ax_prec_right.patch.set_visible(False)

        # Draw cloud background on the right axis (0-100%)
        ax_prec_right.set_ylim(0, 100)
        # Temporarily set limits on left axis for background band placement consistency
        # The draw_cloud_background uses axis limits; adapt to right axis version here:
        def draw_cloud_background_right(axr, times, low, midc, high):
            # thirds in 0-100: [0,33.33], [33.33,66.66], [66.66,100]
            gray = (160/255.0, 160/255.0, 160/255.0)
            for i in range(len(times)-1):
                a_low = max(0.0, min(1.0, low[i] / 100.0))
                a_mid = max(0.0, min(1.0, midc[i] / 100.0))
                a_high = max(0.0, min(1.0, high[i] / 100.0))
                axr.axvspan(times[i], times[i+1], ymin=0.0, ymax=1/3.0, color=gray, alpha=a_low*0.8, zorder=0)
                axr.axvspan(times[i], times[i+1], ymin=1/3.0, ymax=2/3.0, color=gray, alpha=a_mid*0.8, zorder=0)
                axr.axvspan(times[i], times[i+1], ymin=2/3.0, ymax=1.0, color=gray, alpha=a_high*0.8, zorder=0)

        draw_cloud_background_right(ax_prec_right, times, cloud_low, cloud_mid, cloud_high)

        # Probability on right axis (draw first, lower zorder)
        prob_area = ax_prec_right.fill_between(times, precip_prob, 0, color="#a3c8ff", alpha=0.35, zorder=1)
        prob_line, = ax_prec_right.plot(times, precip_prob, color="#4f97ff", linewidth=1.2, zorder=2)

        # Precip bars on left axis - draw last with highest zorder to be on top
        bars = ax_prec_left.bar(
            times, precip, width=0.035, color="#2a74ff", edgecolor="#1b4fae",
            align="center", linewidth=0.6, zorder=30
        )
        # Also make sure left axis is above right axis in stacking
        ax_prec_left.set_zorder(1)
        ax_prec_left.patch.set_visible(False)

        # Labels and limits
        ax_prec_left.set_ylabel("mm/h", fontsize=12)
        ax_prec_left.tick_params(axis='y', labelsize=11)
        # Enforce minimum y scale from 0 to 5 (and auto expand if necessary)
        ymax_precip = max(5.0, max(precip) * 1.4 if len(precip) else 5.0)
        ax_prec_left.set_ylim(0.0, ymax_precip)
        ax_prec_right.set_ylim(0, 100)
        ax_prec_right.set_ylabel("% Clouds / Prob.", fontsize=12, color="#666666")
        ax_prec_right.tick_params(axis='y', colors="#666666", labelsize=11)

        # Keep grids off to reduce clutter
        ax_prec_left.grid(False)
        ax_prec_right.grid(False)

        # Wind chart
        ax_wind.plot(times, wind_speed, color="#6a0dad", linewidth=1.5, zorder=3)
        ax_wind.plot(times, wind_gust, color="#b180d6", linewidth=1.2, zorder=3, linestyle="--", dashes=(4, 3))

        # Wind direction: ASCII arrows at upper part of chart, quantized to 8 directions, every 3 hours
        ymin, ymax = ax_wind.get_ylim()
        arrow_y = ymin + 0.88 * (ymax - ymin)
        for i, t in enumerate(times):
            if t.hour % 3 == 0:
                # Convert meteorological "from" direction to "to" direction
                to_deg = (wind_dir[i] + 180.0) % 360.0
                _, _, sector = Meteo.quantize_dir_8(to_deg)
                txt = Meteo.ascii_arrow_for_sector(sector)
                ax_wind.text(
                    mdates.date2num(t), arrow_y, txt, ha="center", va="center",
                    fontsize=16, color="#4d238a", zorder=5
                )
        ax_wind.set_ylabel("km/h", fontsize=12)
        ax_wind.tick_params(axis='y', labelsize=11)
        ax_wind.grid(True, axis='y', color='#E0E0E0', linewidth=0.5, linestyle='-', alpha=0.7, zorder=10)

        # X axis setup and decorations
        top_full_fmt, abbr_fmt, minor_fmt = Meteo.setup_time_axes(fig, [ax_temp, ax_prec, ax_wind], times, tzname)

        # Top chart: show major/minor tick labels below; hide top labels
        ax_temp.xaxis.set_major_formatter(abbr_fmt)
        ax_temp.tick_params(axis='x', which='major', labeltop=False, labelbottom=True, pad=6)
        ax_temp.tick_params(axis='x', which='minor', labeltop=False, labelbottom=True, pad=6)
        # Manually draw top major labels with full formatter using a secondary axis for top labels
        # Use existing top labels by setting formatter for top: Matplotlib does not separate formatters, so we fake via custom text:
        # Instead, set abbr as major formatter and overlay full date labels as annotation at major tick positions
        tz = zoneinfo.ZoneInfo(tzname)
        # Use datetime bounds for tick generation to avoid relativedelta issues
        start_dt = times[0].astimezone(tz)
        end_dt = times[-1].astimezone(tz)
        locator = mdates.HourLocator(byhour=0, tz=tz)
        # Build list of midnight ticks between start_dt and end_dt
        # Find first midnight >= start_dt
        first_midnight = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if first_midnight < start_dt:
            first_midnight += timedelta(days=1)
        major_locs = []
        tcur = first_midnight
        while tcur <= end_dt:
            major_locs.append(mdates.date2num(tcur))
            tcur += timedelta(days=1)
        eng_weekdays_full = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        # Append the visible end to cover the last (possibly partial) day segment
        major_locs_with_end = list(major_locs)
        major_locs_with_end.append(mdates.date2num(end_dt))
        # Compute center position for each day segment for top labels
        for i in range(len(major_locs_with_end) - 1):
            x0 = major_locs_with_end[i]
            x1 = major_locs_with_end[i + 1]
            x_center = (x0 + x1) / 2.0
            dt = mdates.num2date(x0, tz=tz)  # date of the day starting at x0
            txt = f"{eng_weekdays_full[dt.weekday()]} {dt.strftime('%Y-%m-%d')}"
            ax_temp.text(x_center, 1.02, txt, transform=ax_temp.get_xaxis_transform(), ha="center", va="bottom", fontsize=12, color="#222222", zorder=6)

        # Middle chart: show bottom labels (abbr for majors, HH for minors)
        ax_prec.tick_params(axis='x', which='major', labeltop=False, labelbottom=True, pad=6)
        ax_prec.tick_params(axis='x', which='minor', labeltop=False, labelbottom=True, pad=6)

        # Bottom chart: show bottom labels (abbr for majors, HH for minors)
        ax_wind.tick_params(axis='x', which='major', labeltop=False, labelbottom=True, pad=6)
        ax_wind.tick_params(axis='x', which='minor', labeltop=False, labelbottom=True, pad=6)

        # Remove titles
        ax_temp.set_title("")
        ax_prec.set_title("")
        ax_wind.set_title("")

        # Tight layout adjustments to prevent overlap and remove vertical gaps
        fig.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.08, hspace=0.0)

        # Overall caption-like info (not a title), unobtrusive
        fig.text(0.01, 0.97, f"{self.location_name} • ECMWF IFS HRES 9km • Local time", ha="left", va="top", fontsize=9, color="#333333")
        fig.text(0.99, 0.97, f"Generated: {datetime.now(zoneinfo.ZoneInfo(tzname)).strftime('%Y-%m-%d %H:%M')}", ha="right", va="top", fontsize=8, color="#666666")

        fig.savefig(self.output_file, dpi=130)
        # Also display interactively
        #plt.show()
        plt.close(fig)

    def saveMeteogram(self):
        """Generate and save meteogram to file."""
        Meteo.init()
        data = None

        try:
            self.logger.info(f"Fetching weather data for {self.location_name}...")
            data = self.fetch_open_meteo(self.latitude, self.longitude, self.timezone, self.model)

            self.logger.info("Building meteogram figure...")
            self.build_figure(data)

            self.logger.info(f"Meteogram saved to {self.output_file}")
        except Exception as e:
            self.logger.error(f"Failed: {e}")
            raise
        finally:
            # Aggressive cleanup to prevent memory leaks in long-running process
            if data is not None:
                del data
            plt.close('all')
            gc.collect()

if __name__ == "__main__":
    meteo = Meteo(
        location_name=sys.argv[3],
        latitude=float(sys.argv[1]),
        longitude=float(sys.argv[2]),
        timezone=sys.argv[4],
    #    model="icon_seamless",
        model="ecmwf_ifs",
        output_file="/share/meteogram.png"
    )
    meteo.saveMeteogram()
