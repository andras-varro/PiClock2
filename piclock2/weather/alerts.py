"""
Weather-alert source dispatcher.

Keyless-first: try the US National Weather Service (api.weather.gov), which
covers US points. If a point is outside NWS coverage (nws_alerts.fetch returns
None) and an OpenWeatherMap key is configured, fall back to OWM One Call alerts;
otherwise there are no alerts.

Single public function fetch_alerts(location, owm_key="") -> list[WeatherAlert]
— always returns a list, never raises (alerts are best-effort).
"""

import sys

from weather import nws_alerts, owm_alerts


def fetch_alerts(location, owm_key=""):
    try:
        result = nws_alerts.fetch(location)     # None => no NWS coverage
    except Exception as e:  # noqa: BLE001 - best-effort
        print("piclock2: NWS alerts failed for", location.name, "-", repr(e),
              file=sys.stderr)
        result = None

    if result is not None:
        return result

    if owm_key:
        try:
            return owm_alerts.fetch(location, owm_key)
        except Exception as e:  # noqa: BLE001 - best-effort
            print("piclock2: OWM alerts failed for", location.name, "-", repr(e),
                  file=sys.stderr)
    return []
