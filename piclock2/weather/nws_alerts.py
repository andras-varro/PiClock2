"""
US National Weather Service active-alerts client (api.weather.gov).

Keyless — the API only requires a descriptive User-Agent. Covers the United
States; a point outside coverage (e.g. Europe) returns HTTP 400, which we report
as "no coverage" (None) so the dispatcher can fall back to another source.

One public function: fetch(location) -> list[WeatherAlert] | None
    - list (possibly empty): point is covered; these are the active alerts.
    - None: point is outside NWS coverage.

Runs on a QThreadPool worker thread (see main.WeatherWorker); uses blocking
requests — never call from the GUI thread.
"""

from datetime import datetime

import requests

from models import WeatherAlert, severity_rank

API_URL = "https://api.weather.gov/alerts/active"
HEADERS = {
    "User-Agent": "PiClock2 (https://github.com/n0bel/PiClock)",
    "Accept": "application/geo+json",
}


def fetch(location, timeout=15):
    params = {"point": "%s,%s" % (location.lat, location.lng)}
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=timeout)
    if resp.status_code == 400:
        return None                      # point outside NWS (US) coverage
    resp.raise_for_status()
    feats = (resp.json() or {}).get("features") or []
    alerts = [_parse(f.get("properties") or {}) for f in feats]
    return _dedupe_sort(alerts)


def _parse(p):
    return WeatherAlert(
        event=str(p.get("event") or "Weather Alert"),
        severity=str(p.get("severity") or "Unknown"),
        headline=str(p.get("headline") or ""),
        description=str(p.get("description") or ""),
        instruction=str(p.get("instruction") or ""),
        onset=_epoch(p.get("onset") or p.get("effective")),
        ends=_epoch(p.get("ends") or p.get("expires")),
        sender=str(p.get("senderName") or ""),
    )


def _dedupe_sort(alerts):
    # NWS often issues several alerts for the same event; collapse by event name,
    # keeping the most severe. Then most-severe-first, newest onset next.
    best = {}
    for a in alerts:
        cur = best.get(a.event)
        if cur is None or severity_rank(a.severity) > severity_rank(cur.severity):
            best[a.event] = a
    out = list(best.values())
    out.sort(key=lambda a: (severity_rank(a.severity), a.onset or 0), reverse=True)
    return out


def _epoch(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None
