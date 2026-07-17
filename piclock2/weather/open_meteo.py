"""
Open-Meteo client.

One public function: `fetch(location) -> (CurrentConditions, [HourlyForecast], [DailyForecast])`.

Open-Meteo is free, key-less, and has no rate limit for hobby use. We request
both `current` and `hourly` blocks in one call, with units driven by the
location's `units` ("imperial" | "metric"). `timezone=auto` makes all returned
timestamps local to the queried coordinates, so the hourly strip lines up with
that location's wall clock.

This runs on a QThreadPool worker thread (see main.WeatherService) and uses the
blocking `requests` library — never call it from the GUI thread.
"""

from datetime import datetime, date

import requests

from models import CurrentConditions, HourlyForecast, DailyForecast
from weather.wmo_codes import icon_for, description_for

API_URL = "https://api.open-meteo.com/v1/forecast"

_CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
    "weather_code,pressure_msl,is_day"
)
_HOURLY_FIELDS = (
    "temperature_2m,weather_code,precipitation_probability,precipitation,is_day"
)
_DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max"
)

# Per-unit-system query params.
_UNIT_PARAMS = {
    "imperial": {
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
    },
    "metric": {
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    },
}

N_HOURLY = 12
N_DAILY = 10


def fetch(location, timeout=20):
    """Fetch current conditions + 12h hourly + 10-day daily for a Location.

    Returns (CurrentConditions, [HourlyForecast], [DailyForecast]). Raises on
    network/HTTP errors; the caller (worker) catches and keeps last-good data.
    """
    units = location.units if location.units in _UNIT_PARAMS else "imperial"
    params = {
        "latitude": location.lat,
        "longitude": location.lng,
        "current": _CURRENT_FIELDS,
        "hourly": _HOURLY_FIELDS,
        "daily": _DAILY_FIELDS,
        "timezone": "auto",
        "forecast_days": N_DAILY,
    }
    params.update(_UNIT_PARAMS[units])

    resp = requests.get(API_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    return (
        _parse_current(data, units),
        _parse_hourly(data, units),
        _parse_daily(data, units),
    )


def _parse_current(data, units):
    c = data.get("current", {}) or {}
    code = int(c.get("weather_code", 0) or 0)
    is_day = bool(c.get("is_day", 1))
    temp = _to_float(c.get("temperature_2m"), 0.0)
    return CurrentConditions(
        temperature=temp,
        feels_like=_to_float(c.get("apparent_temperature"), temp),
        humidity=_to_float(c.get("relative_humidity_2m"), 0.0),
        wind_speed=_to_float(c.get("wind_speed_10m"), 0.0),
        wind_direction=_to_float(c.get("wind_direction_10m"), 0.0),
        wind_gust=_opt_float(c.get("wind_gusts_10m")),
        pressure=_opt_float(c.get("pressure_msl")),
        weather_code=code,
        description=description_for(code),
        icon=icon_for(code, is_day),
        units=units,
    )


def _parse_hourly(data, units, count=N_HOURLY):
    h = data.get("hourly", {}) or {}
    times = h.get("time") or []
    if not times:
        return []
    temps = h.get("temperature_2m") or []
    codes = h.get("weather_code") or []
    pops = h.get("precipitation_probability") or []
    precs = h.get("precipitation") or []
    is_days = h.get("is_day") or []

    # Start at the NEXT hour: the current hour's remaining minutes are already
    # covered by the "current conditions" card, so the strip looks ahead.
    start = _current_hour_index(data, times) + 1
    out = []
    for offset in range(count):
        i = start + offset
        if i >= len(times):
            break
        code = int(_at(codes, i, 0) or 0)
        is_day = bool(_at(is_days, i, 1))
        time_iso = _at(times, i, "") or ""
        ts = _parse_iso(time_iso)
        clock_time = ts.strftime("%H:%M") if ts is not None else ""
        out.append(
            HourlyForecast(
                hour_offset=offset + 1,
                temperature=_to_float(_at(temps, i, 0.0), 0.0),
                weather_code=code,
                description=description_for(code),
                icon=icon_for(code, is_day),
                precipitation_probability=_to_float(_at(pops, i, 0.0), 0.0),
                precipitation_amount=_to_float(_at(precs, i, 0.0), 0.0),
                units=units,
                clock_time=clock_time,
                time_iso=time_iso,
            )
        )
    return out


def _parse_daily(data, units, count=N_DAILY):
    d = data.get("daily", {}) or {}
    dates = d.get("time") or []
    if not dates:
        return []
    codes = d.get("weather_code") or []
    tmaxs = d.get("temperature_2m_max") or []
    tmins = d.get("temperature_2m_min") or []
    pops = d.get("precipitation_probability_max") or []

    today = None
    now_str = (data.get("current", {}) or {}).get("time")
    now = _parse_iso(now_str)
    if now is not None:
        today = now.date()

    out = []
    for i in range(min(count, len(dates))):
        iso = _at(dates, i, "") or ""
        code = int(_at(codes, i, 0) or 0)
        out.append(
            DailyForecast(
                date=iso,
                weekday_label=_weekday_label(iso, today),
                weather_code=code,
                description=description_for(code),
                icon=icon_for(code, True),   # daily uses the day-variant artwork
                temp_max=_to_float(_at(tmaxs, i, 0.0), 0.0),
                temp_min=_to_float(_at(tmins, i, 0.0), 0.0),
                precip_prob_max=_to_float(_at(pops, i, 0.0), 0.0),
                units=units,
            )
        )
    return out


def _weekday_label(iso_date, today):
    """'Today' for today's date, else a 3-letter weekday ('Mon')."""
    try:
        dt = date.fromisoformat(iso_date)
    except (ValueError, TypeError):
        return iso_date or ""
    if today is not None and dt == today:
        return "Today"
    return dt.strftime("%a")


def _current_hour_index(data, times):
    """Index of the hourly entry covering 'now' (the current hour).

    hourly times are on-the-hour ISO strings local to the location;
    current.time is the actual local time. The current hour is the last
    hourly entry that is <= now.
    """
    now_str = (data.get("current", {}) or {}).get("time")
    now = _parse_iso(now_str)
    if now is None:
        return 0
    best = 0
    for i, t in enumerate(times):
        ts = _parse_iso(t)
        if ts is None:
            continue
        if ts <= now:
            best = i
        else:
            break
    return best


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _at(seq, i, default):
    try:
        v = seq[i]
    except (IndexError, TypeError):
        return default
    return default if v is None else v


def _to_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _opt_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
