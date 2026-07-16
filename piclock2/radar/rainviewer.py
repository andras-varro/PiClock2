"""
Rainviewer v2 API client.

The legacy app hit `tilecache.rainviewer.com/v2/radar/<timestamp>/...` URLs
directly; rainviewer changed that so you must first fetch an index JSON to
learn the current host + per-frame paths, then build tile URLs from those.

    index = fetch_index()
    host, frames = select_frames(index, past_count=6)
    url = tile_url(host, frames[0].path, zoom, x, y)
"""

from dataclasses import dataclass

import requests

INDEX_URL = "https://api.rainviewer.com/public/weather-maps.json"

# rainviewer tile styling knobs (same defaults the old Config used).
COLOR = 6       # color scheme
SMOOTH = 1      # smoothed pixels
SNOW = 1        # show snow as a separate color
TILE_SIZE = 256


@dataclass
class Frame:
    time: int       # unix seconds
    path: str       # e.g. "/v2/radar/cdc279f046d2"
    kind: str       # "past" | "now" | "nowcast"


def fetch_index(timeout=10):
    """GET the weather-maps index. Returns the parsed dict (raises on failure)."""
    resp = requests.get(INDEX_URL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def select_frames(index, past_count=6):
    """
    Turn the index into (host, [Frame]) ordered oldest -> newest -> nowcast.

    The most recent observed frame (last of radar.past) is tagged "now";
    earlier observed frames are "past"; nowcast frames are "nowcast".
    `past_count` caps how many observed frames to keep (most recent first).
    """
    host = index.get("host", "https://tilecache.rainviewer.com")
    radar = index.get("radar") or {}
    past = list(radar.get("past") or [])
    nowcast = list(radar.get("nowcast") or [])

    if past_count and len(past) > past_count:
        past = past[-past_count:]

    frames = []
    for i, f in enumerate(past):
        kind = "now" if i == len(past) - 1 else "past"
        frames.append(Frame(time=int(f["time"]), path=str(f["path"]), kind=kind))
    for f in nowcast:
        frames.append(Frame(time=int(f["time"]), path=str(f["path"]), kind="nowcast"))

    return host, frames


def tile_url(host, path, zoom, x, y,
             color=COLOR, smooth=SMOOTH, snow=SNOW, size=TILE_SIZE):
    """Build one rainviewer tile URL: {host}{path}/{size}/{z}/{x}/{y}/{color}/{smooth}_{snow}.png"""
    return "%s%s/%d/%d/%d/%d/%d/%d_%d.png" % (
        host, path, size, zoom, x, y, color, smooth, snow
    )
