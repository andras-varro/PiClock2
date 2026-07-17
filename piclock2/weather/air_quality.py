"""
Open-Meteo Air Quality client.

Separate host from the weather forecast API. We request BOTH the US and
European AQI in one call (negligible extra cost) and let the display layer pick
the scale per location. The endpoint forecasts at most 7 days and has no daily
aggregation, so we roll hourly values up to a per-day maximum ourselves (the
day's peak AQI is the meaningful daily summary).

`fetch_air_quality(location)` returns an `AirQuality` with:
    current : {"us": int|None, "eu": int|None}
    hourly  : {iso_hour_str: {"us": int|None, "eu": int|None}}
    daily   : {iso_date_str: {"us": int|None, "eu": int|None}}   # day max

Runs on a QThreadPool worker thread via blocking `requests` — never on the GUI
thread. Raises on network/HTTP errors; the caller treats it best-effort.
"""

import requests

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

_FIELDS = "us_aqi,european_aqi"
FORECAST_DAYS = 7          # endpoint maximum


class AirQuality:
    def __init__(self, current, hourly, daily):
        self.current = current      # {"us": .., "eu": ..}
        self.hourly = hourly        # {iso_hour: {"us": .., "eu": ..}}
        self.daily = daily          # {iso_date: {"us": .., "eu": ..}}


def fetch_air_quality(location, timeout=20):
    params = {
        "latitude": location.lat,
        "longitude": location.lng,
        "current": _FIELDS,
        "hourly": _FIELDS,
        "timezone": "auto",
        "forecast_days": FORECAST_DAYS,
    }
    resp = requests.get(API_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    cur = data.get("current", {}) or {}
    current = {"us": _aqi(cur.get("us_aqi")), "eu": _aqi(cur.get("european_aqi"))}

    h = data.get("hourly", {}) or {}
    times = h.get("time") or []
    us = h.get("us_aqi") or []
    eu = h.get("european_aqi") or []

    hourly = {}
    daily = {}
    for i, t in enumerate(times):
        if not t:
            continue
        u = _aqi(_at(us, i))
        e = _aqi(_at(eu, i))
        hourly[t] = {"us": u, "eu": e}
        day = t[:10]                       # "YYYY-MM-DDTHH:MM" -> "YYYY-MM-DD"
        agg = daily.setdefault(day, {"us": None, "eu": None})
        agg["us"] = _max(agg["us"], u)
        agg["eu"] = _max(agg["eu"], e)

    return AirQuality(current, hourly, daily)


def _at(seq, i):
    try:
        return seq[i]
    except (IndexError, TypeError):
        return None


def _aqi(v):
    """AQI as an int, or None if missing/unparseable."""
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _max(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b
