from dataclasses import dataclass, field
from typing import List, Optional

# 16-point compass, N at 0°, clockwise.
_COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def wind_compass(degrees) -> str:
    """Convert a wind direction in degrees to a 16-point compass label."""
    try:
        d = float(degrees)
    except (TypeError, ValueError):
        return ""
    return _COMPASS[int((d % 360) / 22.5 + 0.5) % 16]


# Alert severity ordering + colors, shared by the model layer (sort/de-dupe)
# and the UI (badge / banner / overlay coloring) so there is one mapping.
SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
_SEVERITY_COLOR = {
    "Extreme": "#d50000",
    "Severe": "#ff3b30",
    "Moderate": "#ff9500",
    "Minor": "#ffcc00",
    "Unknown": "#8e8e93",
}


def severity_rank(sev) -> int:
    return SEVERITY_RANK.get(sev, 0)


def severity_color(sev) -> str:
    return _SEVERITY_COLOR.get(sev, "#8e8e93")


def severity_text_color(sev) -> str:
    """Readable text color over a severity-colored background."""
    # Yellow (Minor) and gray (Unknown) need dark text; the reds/orange take white.
    return "#000000" if sev in ("Minor", "Unknown") else "#ffffff"


# --- Air Quality (AQI) ---------------------------------------------------
#
# Open-Meteo exposes two AQI scales; we keep both per reading and pick one per
# location. US AQI (0-500, EPA bands) reads naturally for US spots; European
# AQI (0-100+, EEA bands) for European ones. Only the colored *dot* is tinted
# by band — the numeral stays in the theme color so it's always legible.

# (upper_bound_inclusive, color) ascending; last entry is the open-ended top band.
_US_AQI_BANDS = (
    (50, "#00e400"),    # Good
    (100, "#ffff00"),   # Moderate
    (150, "#ff7e00"),   # Unhealthy for sensitive groups
    (200, "#ff0000"),   # Unhealthy
    (300, "#8f3f97"),   # Very unhealthy
    (10 ** 9, "#7e0023"),  # Hazardous
)
_EU_AQI_BANDS = (
    (20, "#50f0e6"),    # Good
    (40, "#50ccaa"),    # Fair
    (60, "#f0e641"),    # Moderate
    (80, "#ff5050"),    # Poor
    (100, "#960032"),   # Very poor
    (10 ** 9, "#7d2181"),  # Extremely poor
)


def aqi_scale_for(location) -> str:
    """Which AQI scale to display for a location: 'us' or 'european'.

    Honors an explicit per-location override; otherwise derives from units
    (metric -> European, imperial -> US).
    """
    override = (getattr(location, "aqi_scale", "") or "").strip().lower()
    if override in ("us", "european"):
        return override
    return "european" if getattr(location, "units", "imperial") == "metric" else "us"


def aqi_value(obj, scale):
    """Pull the AQI int for the given scale off any model carrying aqi_us/aqi_eu."""
    if obj is None:
        return None
    return obj.aqi_eu if scale == "european" else obj.aqi_us


def aqi_color(value, scale) -> str:
    """Band color for an AQI value on the given scale."""
    bands = _EU_AQI_BANDS if scale == "european" else _US_AQI_BANDS
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "#8e8e93"
    for upper, color in bands:
        if v <= upper:
            return color
    return bands[-1][1]


def aqi_dot_html(value, scale) -> str:
    """Rich-text 'colored dot + number' for a QLabel, or '' when no value.

    Only the dot is tinted (band color); the number inherits the label's own
    color so it stays legible on the dark theme regardless of band.
    """
    if value is None:
        return ""
    return '<span style="color:{}">&#9679;</span> {}'.format(
        aqi_color(value, scale), int(value))


@dataclass
class Location:
    name: str
    lat: float
    lng: float
    units: str = "imperial"
    radar_zoom: int = 8
    aqi_scale: str = ""          # "" = derive from units; else "us" | "european"


@dataclass
class CurrentConditions:
    temperature: float
    feels_like: float
    humidity: float
    wind_speed: float
    wind_direction: float
    wind_gust: Optional[float]
    pressure: Optional[float]
    weather_code: int
    description: str
    icon: str
    units: str
    aqi_us: Optional[int] = None
    aqi_eu: Optional[int] = None


@dataclass
class HourlyForecast:
    hour_offset: int
    temperature: float
    weather_code: int
    description: str
    icon: str
    precipitation_probability: float
    precipitation_amount: float
    units: str
    clock_time: str = ""        # local wall-clock label, e.g. "14:00"
    time_iso: str = ""          # full ISO hour (for matching AQI by time)
    aqi_us: Optional[int] = None
    aqi_eu: Optional[int] = None


@dataclass
class DailyForecast:
    date: str                   # ISO "YYYY-MM-DD" (local to the location)
    weekday_label: str          # "Today", "Mon", "Tue", ...
    weather_code: int
    description: str
    icon: str
    temp_max: float
    temp_min: float
    precip_prob_max: float
    units: str
    aqi_us: Optional[int] = None
    aqi_eu: Optional[int] = None


@dataclass
class WeatherAlert:
    event: str                       # e.g. "Extreme Heat Watch"
    severity: str                    # Extreme | Severe | Moderate | Minor | Unknown
    headline: str = ""
    description: str = ""
    instruction: str = ""
    onset: Optional[float] = None    # epoch seconds
    ends: Optional[float] = None     # epoch seconds
    sender: str = ""


@dataclass
class LocationData:
    location: Location
    current: Optional[CurrentConditions] = None
    hourly: List[HourlyForecast] = field(default_factory=list)
    daily: List[DailyForecast] = field(default_factory=list)
    alerts: List[WeatherAlert] = field(default_factory=list)
    last_updated: Optional[float] = None
