"""
openpane.core
Location detection, weather fetching, asset selection.
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class LocationInfo:
    city: str
    country: str
    lat: float
    lon: float
    timezone: str


@dataclass
class WeatherInfo:
    state: str       # clear / cloudy / rain / snow / thunder
    season: str      # spring / summer / autumn / winter
    tod: str         # dawn / day / dusk / night
    temp: float
    city: str
    country: str


# ── HTTP helper ─────────────────────────────────────────────
def fetch_json(url: str, timeout: int = 4) -> Optional[dict]:
    """Fetch URL and return parsed JSON, or None on error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "openpane/0.3"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


# ── Weather helpers ─────────────────────────────────────────
def wmo_to_state(code: int) -> str:
    """Convert Open-Meteo WMO weather code to a simple state string."""
    if code == 0:
        return "clear"
    elif code in (1, 2, 3):
        return "cloudy"
    elif code in range(51, 68) or code in range(80, 83):
        return "rain"
    elif code in range(71, 78):
        return "snow"
    elif code in range(95, 100):
        return "thunder"
    return "clear"


def get_season(month: int, lat: float) -> str:
    """Determine season from month and latitude (flips for southern hemisphere)."""
    if lat < 0:
        month = (month + 6 - 1) % 12 + 1
    if month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    elif month in (9, 10, 11):
        return "autumn"
    return "winter"


def time_of_day(hour: int) -> str:
    """Return time-of-day label for a given hour (0–23)."""
    if 5 <= hour < 8:
        return "dawn"
    elif 8 <= hour < 18:
        return "day"
    elif 18 <= hour < 21:
        return "dusk"
    return "night"


# ── Location & weather fetching ─────────────────────────────
def get_location() -> Optional[LocationInfo]:
    """Detect current city via IP geolocation."""
    data = fetch_json("http://ip-api.com/json/?fields=city,country,lat,lon,timezone,status")
    if data and data.get("status") == "success":
        return LocationInfo(
            city=data.get("city", "Unknown"),
            country=data.get("country", ""),
            lat=float(data.get("lat", 37.5)),
            lon=float(data.get("lon", 127.0)),
            timezone=data.get("timezone", "Asia/Seoul"),
        )
    return None


def get_weather(loc: LocationInfo) -> Optional[WeatherInfo]:
    """Fetch real-time weather from Open-Meteo for the given location."""
    from datetime import datetime, timezone, timedelta

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc.lat}&longitude={loc.lon}"
        f"&current=temperature_2m,weathercode"
        f"&timezone=auto"
    )
    data = fetch_json(url)
    if not data:
        return None

    curr = data.get("current", {})
    code = int(curr.get("weathercode", 0))
    temp = float(curr.get("temperature_2m", 20))

    offset_seconds = int(data.get("utc_offset_seconds", 0))
    local_dt = datetime.now(timezone(timedelta(seconds=offset_seconds)))

    return WeatherInfo(
        state=wmo_to_state(code),
        season=get_season(local_dt.month, loc.lat),
        tod=time_of_day(local_dt.hour),
        temp=temp,
        city=loc.city,
        country=loc.country,
    )


# ── Asset selection ─────────────────────────────────────────
def pick_asset(weather: WeatherInfo) -> str:
    """Choose the appropriate asset name for the current weather."""
    if weather.tod == "night" and weather.state in ("clear", "cloudy"):
        return "night"
    if weather.state == "rain" or weather.state == "thunder":
        return "rain"
    if weather.state == "snow":
        return "snow"
    if weather.season == "spring":
        return "spring"
    return "clear"
