import os
import sys
import toml

from models import Location


class Config:
    def __init__(self, path):
        with open(path, "r") as f:
            data = toml.load(f)

        display = data.get("display", {})
        self.width = int(display.get("width", 1280))
        self.height = int(display.get("height", 720))
        self.fullscreen = bool(display.get("fullscreen", False))

        mapbox = data.get("mapbox", {})
        self.mapbox_key = mapbox.get("key", "")
        self.mapbox_style = mapbox.get("style", "mapbox/satellite-streets-v10")

        # Optional. Weather alerts are keyless via NWS for US points; an OWM key
        # (One Call 3.0) is only needed to also get alerts for non-US locations.
        owm = data.get("openweathermap", {})
        self.owm_key = owm.get("key", "")

        clock = data.get("clock", {})
        self.clock_use_utc = bool(clock.get("use_utc", False))
        self.clock_locale = clock.get("locale", "")

        locs = data.get("locations", [])
        if not locs:
            raise ValueError("config must define at least one [[locations]]")
        self.locations = [
            Location(
                name=str(l["name"]),
                lat=float(l["lat"]),
                lng=float(l["lng"]),
                units=str(l.get("units", "imperial")),
                radar_zoom=int(l.get("radar_zoom", 8)),
                aqi_scale=str(l.get("aqi_scale", "")),
            )
            for l in locs
        ]


def load_default():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.environ.get("PICLOCK2_CONFIG"),
        os.path.join(here, "config.toml"),
        os.path.expanduser("~/.config/piclock2/config.toml"),
        os.path.join(here, "config.example.toml"),
    ):
        if candidate and os.path.isfile(candidate):
            print("piclock2: loading config from", candidate, file=sys.stderr)
            return Config(candidate)
    raise FileNotFoundError("no config.toml found (looked in cwd, ~/.config/piclock2, example)")
