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


@dataclass
class Location:
    name: str
    lat: float
    lng: float
    units: str = "imperial"
    radar_zoom: int = 8


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
    alerts: List[WeatherAlert] = field(default_factory=list)
    last_updated: Optional[float] = None
