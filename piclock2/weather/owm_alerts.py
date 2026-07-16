"""
OpenWeatherMap One Call 4.0 alerts client — optional, non-US fallback.

One Call 4.0 (included in the paid "One Call by Call" subscription) returns
alerts in two steps:
  1. /data/4.0/onecall/current      -> data[0].alerts is a list of alert *IDs*
  2. /data/4.0/onecall/alert/{id}   -> that alert's detail

Detail fields: sender_name, event (often empty -> we fall back to `tags`),
start, end, and description as a list of {language, description} objects (we
prefer English). OWM provides no severity grade, so these surface as "Unknown".

Used only for points outside NWS coverage (see weather/alerts.py) when an
openweathermap.key is configured. Only the active non-US location(s) hit this,
so the per-cycle call count stays small (1 + one per distinct alert).
"""

import requests

from models import WeatherAlert

CURRENT_URL = "https://api.openweathermap.org/data/4.0/onecall/current"
ALERT_URL = "https://api.openweathermap.org/data/4.0/onecall/alert/%s"
MAX_ALERTS = 6          # cap detail fetches — each is a billed API call


def fetch(location, key, timeout=15):
    if not key:
        return []
    r = requests.get(
        CURRENT_URL,
        params={"lat": location.lat, "lon": location.lng, "appid": key},
        timeout=timeout)
    if r.status_code in (401, 403):
        return []           # key not subscribed to the One Call by Call plan
    r.raise_for_status()
    rows = (r.json() or {}).get("data") or []
    ids = (rows[0].get("alerts") if rows else None) or []

    out, seen = [], set()
    for aid in ids[:MAX_ALERTS]:
        a = _detail(aid, key, timeout)
        if a is None or a.event in seen:   # collapse repeats (e.g. per-day reissues)
            continue
        seen.add(a.event)
        out.append(a)
    return out


def _detail(aid, key, timeout):
    r = requests.get(ALERT_URL % aid, params={"appid": key}, timeout=timeout)
    if r.status_code != 200:
        return None
    d = r.json() or {}
    event = (d.get("event") or "").strip()
    if not event:
        tags = d.get("tags") or []
        event = ", ".join(str(t) for t in tags) if tags else "Weather Alert"
    return WeatherAlert(
        event=event,
        severity="Unknown",          # OWM 4.0 provides no severity grade
        headline=event,
        description=_pick_description(d.get("description")),
        onset=_num(d.get("start")),
        ends=_num(d.get("end")),
        sender=str(d.get("sender_name") or ""),
    )


def _pick_description(desc):
    """description is a list of {language, description}; prefer English."""
    if isinstance(desc, str):
        return desc
    if not isinstance(desc, list) or not desc:
        return ""
    for item in desc:
        if str(item.get("language", "")).lower().startswith("en"):
            return item.get("description", "") or ""
    return desc[0].get("description", "") or ""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
