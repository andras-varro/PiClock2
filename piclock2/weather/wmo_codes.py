"""
WMO weather code -> icon stem + short English description.

Open-Meteo returns WMO interpretation codes (0..99) in `weather_code`.
We map those onto the artwork that actually exists in
`assets/icons-lightblue/` (DarkSky-era names, NOT WMO numbers):

    clear-day, clear-night, cloudy, fog, partly-cloudy-day,
    partly-cloudy-night, rain, sleet, snow, thunderstorm, wind

`icon_for(code, is_day)` returns a filename stem (no ".png"); the UI joins
it with the icons dir. Codes with day/night artwork (clear, partly cloudy)
resolve via `is_day`; everything else has a single icon.
"""

# WMO code -> base icon name. "clear" / "partly-cloudy" are resolved to their
# day/night variants in icon_for(); all others are used verbatim.
_WMO_TO_ICON_BASE = {
    0: "clear",          # Clear sky
    1: "clear",          # Mainly clear
    2: "partly-cloudy",  # Partly cloudy
    3: "cloudy",         # Overcast
    45: "fog",           # Fog
    48: "fog",           # Depositing rime fog
    51: "rain",          # Drizzle: light
    53: "rain",          # Drizzle: moderate
    55: "rain",          # Drizzle: dense
    56: "sleet",         # Freezing drizzle: light
    57: "sleet",         # Freezing drizzle: dense
    61: "rain",          # Rain: slight
    63: "rain",          # Rain: moderate
    65: "rain",          # Rain: heavy
    66: "sleet",         # Freezing rain: light
    67: "sleet",         # Freezing rain: heavy
    71: "snow",          # Snow fall: slight
    73: "snow",          # Snow fall: moderate
    75: "snow",          # Snow fall: heavy
    77: "snow",          # Snow grains
    80: "rain",          # Rain showers: slight
    81: "rain",          # Rain showers: moderate
    82: "rain",          # Rain showers: violent
    85: "snow",          # Snow showers: slight
    86: "snow",          # Snow showers: heavy
    95: "thunderstorm",  # Thunderstorm: slight or moderate
    96: "thunderstorm",  # Thunderstorm with slight hail
    99: "thunderstorm",  # Thunderstorm with heavy hail
}

WMO_TO_DESCRIPTION = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm, hail",
    99: "Thunderstorm, hail",
}


def icon_for(code, is_day=True):
    """Return the icon filename stem for a WMO code (no extension)."""
    base = _WMO_TO_ICON_BASE.get(int(code), "cloudy")
    if base == "clear":
        return "clear-day" if is_day else "clear-night"
    if base == "partly-cloudy":
        return "partly-cloudy-day" if is_day else "partly-cloudy-night"
    return base


def description_for(code):
    """Return a short English description for a WMO code."""
    return WMO_TO_DESCRIPTION.get(int(code), "—")
