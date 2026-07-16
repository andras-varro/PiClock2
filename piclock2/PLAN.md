# PiClock 2 — Rewrite Plan

## Context

The user runs a modified PiClock fork ([PyQtPiClock.py](c:/work/repos/PiClock/Clock/PyQtPiClock.py))
on a Raspberry Pi 3 B+ (192.168.50.56) at 1920×1080, viewed via VNC on
multiple lower-res clients (Steelcase RoomWizard 800×480 with bilinear-scaling
custom VNC client, an old iPad, and the Pi's own HDMI screen). Three concrete
problems prompted this rewrite:

1. **Radar overlay broken** — rainviewer changed its API; the deployed app hits the legacy
   `tilecache.rainviewer.com/v2/radar/<timestamp>/...` URLs which return empty bodies,
   producing `IndexError: list index out of range` in `Radar.rtick` ([PyQtPiClock.py:1643](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L1643)).
   Current API requires fetching `api.rainviewer.com/public/weather-maps.json` first
   to learn valid host + paths + frame timestamps.
2. **Forecast is in 3-hour steps** — OpenWeatherMap's free `/forecast` endpoint is
   structurally 3-hourly; OWM removed free OneCall, so true hourly requires a different
   provider. User has already locally patched the app to show 9 cards but the cadence is wrong.
3. **Layout designed for 1440×900 desktop** — date is above the clock, sun/moon below;
   the user wants the clock larger and these elements relocated *inside* the dial.

The stack is **end-of-life**: Python 2.7 + PyQt4 on Raspbian Buster (Python 3.7 also
available on the device). User plans a future Proxmox migration off the Pi 3.

User also wants **multi-location support**: 3 locations to start (Princeton NJ home,
Long Branch NJ, Budapest HU), tappable to switch the active location → radar +
forecast + sun/moon refocus on that location.

Cost-conscious: target ≤200k context per session. This plan IS the handoff doc —
each phase is independently resumable in a fresh session by re-reading this file.

## Goals

1. Working radar (rainviewer v2, with past + nowcast frames).
2. True hourly forecast (12 hours) from Open-Meteo (free, no API key, no rate-limit concern).
3. Larger centered analog clock with date arc'd inside the dial top and sun/moon arc'd inside the dial bottom.
4. Multi-location: left column shows N location cards; tap to make one active; radar/hourly/sun-moon switch.
5. Small radar always visible (~280×280); tap → full-screen radar with timestamp overlay.
6. Forecast-vs-past signaling on small radar via colored border (green=past, white=now, amber=nowcast).
7. Python 3 + PyQt5 (apt-installable on Buster; easy port to PyQt6/Qt6 on Proxmox later).

## Non-Goals

- Pan/zoom on the radar (too much for hobby scope; multi-location cards substitute).
- Touch/keyboard sidecars (TempServer, NeoPixel, GPIO, IR, NOAA stream) — user opted out.
- Backwards compatibility with the old `Config.py` / `ApiKeys.py` files.
- Replacing the artwork — reuse n0bel's neon PNGs as-is.

## Stack

| Concern         | Choice |
|-----------------|--------|
| Language        | Python 3.7+ (Buster ships 3.7; Proxmox VM will get newer) |
| GUI             | PyQt5 (`apt install python3-pyqt5`) — no pip needed |
| HTTP            | `requests` on a `QThreadPool` worker |
| Weather         | Open-Meteo (`https://api.open-meteo.com/v1/forecast`) — free, no key, true hourly + daily, WMO weather codes |
| Radar tiles     | rainviewer v2 (`api.rainviewer.com/public/weather-maps.json` → returned host + path) — free, no key, includes 2h past + 30 min nowcast |
| Basemap         | Mapbox Static Images (user already has `mbapi` key) |
| Config          | TOML (`tomli` for 3.7; stdlib `tomllib` on 3.11+) at `~/.config/piclock2/config.toml` |
| Sun position    | Reuse the `suntimes` class from PyQtPiClock.py:37-142 (port to Py3, mostly print → print() and `/` → `//` where it's int math) |
| Moon phase      | Reuse `moon_phase()` from PyQtPiClock.py:146-152 (no changes needed) |
| Mercator math   | Reuse [GoogleMercatorProjection.py](c:/work/repos/PiClock/Clock/GoogleMercatorProjection.py) wholesale — already Py2/3 compatible |

## Target Layout (1280×720 logical, rendered at native, VNC scales)

```
┌─────────────────┬──────────────────────────┬──────────────────┐
│ ●Princeton 68°F │                          │ now      68°F 🌧 │
│   light rain    │                          │ +1h      67°F 🌧 │
│ ─────────────── │                          │ +2h      66°F ☁  │
│  Long Branch    │      BIG ANALOG          │ +3h      65°F ☁  │
│  71°F overcast  │       CLOCK              │ +4h      63°F ☀  │
│ ─────────────── │   ◜ Sat Jun 27 2026 ◝   │ +5h      62°F ☀  │
│  Budapest 21°C  │                          │ +6h      66°F ☀  │
│  clear          │  ◟ ☀05:31 ☾Waxing  ◞    │ +7h      70°F ☀  │
│                 │                          │ +8h      73°F ☀  │
│ ┌─────────────┐ │                          │ +9h      75°F ☀  │
│ │ small radar │ │                          │ +10h     77°F ☀  │
│ │   280×280   │ │                          │ +11h     76°F ☁  │
│ │ (colored    │ │                          │ +12h     74°F ☁  │
│ │  border by  │ │                          │                  │
│ │  frame age) │ │                          │                  │
│ └─────────────┘ │                          │                  │
└─────────────────┴──────────────────────────┴──────────────────┘
   ~280 wide              ~720 wide                ~280 wide
```

- Clock is centered in the middle column, ~560 px diameter (vs current ~400).
- Date is rendered along an arc following the inside top of the dial.
- Sun rise/set + moon phase rendered along an arc following the inside bottom of the dial.
- Both arcs follow the *active location's* day/sun/moon — switching location updates them.
- The clock itself stays on Pi local time always (wall clock semantics).
- Location card highlight: thin colored border + filled dot before the name.
- Small radar border: green (past frame), white (now), amber (nowcast). 4 px solid.

**Full-screen radar**: tap small radar → that widget expands to fill the whole window;
all other widgets hide. Same animation, plus a `−1h 20m · light rain expected`-style
timestamp+condition overlay in a corner. Tap anywhere → restore.

## Directory Layout

```
piclock2/
  main.py                  # QApplication, MainWindow, layout, top-level timers
  app_state.py             # Active location index, signal bus (LocationChanged)
  config.py                # TOML loader, defaults, validation
  config.example.toml      # Documented example with the 3 starter locations
  models.py                # @dataclass: Location, CurrentConditions, HourlyForecast, RadarFrame
  weather/
    open_meteo.py          # HTTP client; returns CurrentConditions + 12×HourlyForecast
    wmo_codes.py           # WMO weather code → existing icons-lightblue/*.png filename
  radar/
    rainviewer.py          # Fetch index JSON, build tile URLs for past+nowcast
    basemap.py             # Mapbox Static Images URL builder (port from PyQtPiClock.mapboxurl)
    compositor.py          # Composite tiles + basemap into a QPixmap per frame
  ui/
    location_card.py       # Clickable QWidget: icon, city, temp, condition
    location_column.py     # Vertical stack of LocationCards + the small radar below
    clock_face.py          # Big analog clock with arc'd date + arc'd sun/moon overlay
    hourly_strip.py        # 12 hourly forecast rows
    radar_widget.py        # Small radar with colored border; emits clicked() signal
    radar_fullscreen.py    # Full-screen overlay with timestamp; emits dismissed()
  assets/                  # Symlinks (or copies) to ../Clock/images/* and ../Clock/icons-lightblue/*
  PLAN.md                  # Copy of this plan file
  README.md                # Install + run + config notes
  deploy.sh                # rsync to pi@192.168.50.56:/home/pi/piclock2/
  piclock2.desktop         # Autostart entry (replaces PiClock.desktop when ready)
```

## Module Responsibilities

### `weather/open_meteo.py`

One function: `fetch(location: Location) -> tuple[CurrentConditions, list[HourlyForecast]]`.
Endpoint: `https://api.open-meteo.com/v1/forecast?latitude=X&longitude=Y&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,pressure_msl&hourly=temperature_2m,weather_code,precipitation_probability,precipitation&timezone=auto&forecast_days=2&temperature_unit={unit}&wind_speed_unit={unit}`.
Slice hourly to next 12 entries after current hour.

### `weather/wmo_codes.py`

Lookup `WMO_TO_ICON: dict[int, str]` mapping each WMO weather code (0..99) to an icon
filename in `icons-lightblue/` (e.g. 0→"01d", 3→"04d", 95→"11d"). Also `WMO_TO_DESCRIPTION`
for English short text. Two tables, ~30 entries each, hardcoded module-level.

### `radar/rainviewer.py`

`fetch_index() -> RainviewerIndex` hits the JSON endpoint, returns `host`, `radar.past`
(list of `{time, path}`), `radar.nowcast` (same). `tile_url(host, path, z, x, y, color, smooth, snow)`
formats `{host}{path}/256/{z}/{x}/{y}/{color}/{smooth}_{snow}.png`. Caller decides
how many past frames to use (default: all available — typically 12 × 10 min = 2h)
plus all nowcast (typically 3 × 10 min = 30 min).

### `radar/basemap.py`

`mapbox_url(center: LatLng, zoom: int, width: int, height: int, style: str, marker: bool) -> str`
ported from [PyQtPiClock.py:1841-1855](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L1841-L1855).
Returns the static-images URL with `@2x` for retina (so VNC clients still see crisp pixels when
upscaled). Mapbox key from config.

### `radar/compositor.py`

`build_frame(basemap: QPixmap, radar_tiles: list[QImage], corner_tiles: dict) -> QPixmap`.
Composites the 3×3 (or whatever) grid of 256×256 rainviewer tiles over the basemap,
clipped to the widget rect. Translates the existing logic from
[PyQtPiClock.py:1786-1828](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L1786-L1828).

### `ui/clock_face.py`

`ClockFace(QWidget)` paints in `paintEvent`:
1. The clock background pixmap (scaled to fit).
2. The clock face PNG.
3. Hour, minute, second hands (rotated QPixmaps — same approach as
   [PyQtPiClock.py tick()](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L155-L237)).
4. Date text along an arc inside the top of the dial (use `QPainter.drawText`
   with rotation, char by char, along a circle of radius `0.8 × clock_radius`).
5. Sun rise/set + moon phase along the bottom arc, same technique.
Drives a 1Hz QTimer for second-hand update; date/moon/sun only updated when
they change (track `lastmin`, `lastday`).

### `ui/location_card.py`

`LocationCard(QWidget)` shows icon (32×32), city name, temp, brief condition.
Stylesheet flips on `active` property: highlighted border + dot prefix when True.
Emits `clicked = pyqtSignal()` via `mousePressEvent`. Receives data via
`set_conditions(CurrentConditions)`.

### `ui/location_column.py`

Vertical layout: N × LocationCard, then a stretch, then the `RadarWidget`.
Wires `LocationCard.clicked` → `AppState.set_active(i)`.

### `ui/radar_widget.py`

Small (~280×280) widget that paints the latest composited radar frame.
On a QTimer (every 500 ms) advances `displayed_frame`, redraws.
Frame border color depends on `frames[displayed_frame].kind` (`past` | `now` | `nowcast`).
Listens for `AppState.location_changed` to refetch with the new center.
Emits `clicked = pyqtSignal()` for fullscreen toggle.

### `ui/radar_fullscreen.py`

Same paint logic as RadarWidget but full-window. Adds a `QLabel` overlay
in the top-left with `−1h 20m · 2026-06-27 19:08 UTC` style timestamp,
derived from the displayed frame's `time` field. Emits `dismissed` on click.

### `app_state.py`

Tiny module-level singleton-ish QObject:

```python
class AppState(QObject):
    location_changed = pyqtSignal(int)
    def __init__(self, n_locations):
        ...
        self._active = 0
    def set_active(self, i):
        if i != self._active:
            self._active = i
            self.location_changed.emit(i)
```

All widgets that care subscribe.

### `main.py`

- Load config.
- Build `AppState`, location list.
- Build `MainWindow` (`QStackedWidget` with two pages: normal layout + fullscreen radar).
- Spawn the data timers (weather refresh every 30 min per location with jitter;
  radar refresh every 5 min globally).
- Each fetch runs on `QThreadPool` (HTTP off the GUI thread); results posted back
  via `pyqtSignal` to widgets.
- F4 closes (preserve current keybinding); click on radar widget shows fullscreen page.

## Config Schema (`config.toml`)

```toml
[display]
width = 1280
height = 720
fullscreen = true   # false in dev on Windows

[mapbox]
key = "pk.xxx"
style = "mapbox/satellite-streets-v10"

[clock]
use_utc = false
locale = ""          # empty = system default

[[locations]]
name = "Princeton, NJ"
lat = 40.296919
lng = -74.771514
units = "imperial"   # imperial | metric
radar_zoom = 8

[[locations]]
name = "Long Branch, NJ"
lat = 40.30428
lng = -73.99236
units = "imperial"
radar_zoom = 8

[[locations]]
name = "Budapest, HU"
lat = 47.49835
lng = 19.04045
units = "metric"
radar_zoom = 8
```

First `[[locations]]` is active at startup.

## Implementation Phases (each independently resumable)

Each phase is a separate session if needed. Phase boundary = commit + working app.
After each phase, run on Pi via SSH and have user verify visually.

### Phase 1 — Skeleton + clock face only (no live data)

**Deliverable**: `python3 piclock2/main.py` runs on the Pi, shows the 3-column
layout with: placeholder location cards (static text), big working analog clock
with date arc top + sun/moon arc bottom inside the dial (sun/moon computed from
config's first location), placeholder hourly cards (static text), placeholder
gray rectangle where small radar will go.

**Files**: `main.py`, `app_state.py`, `config.py`, `config.example.toml`, `models.py`,
`ui/clock_face.py`, `ui/location_card.py` (no data binding yet),
`ui/location_column.py`, `ui/hourly_strip.py` (placeholder), `assets/` symlinks,
`README.md`.

**Verification**: SSH to Pi, `cd /home/pi/piclock2 && python3 main.py`. User confirms
clock displays, date/sun/moon are visibly inside the dial as arcs, no crashes.
We're not stopping the old app yet — run in windowed mode for this phase.

**Estimated context**: ~40k. Safe to fit in one session.

### Phase 2 — Open-Meteo + live location cards + hourly strip

**Deliverable**: Location cards show real current conditions. Tap → active state
flips; hourly strip on the right updates to active location.

**Files**: `weather/open_meteo.py`, `weather/wmo_codes.py`, fill in `LocationCard`
data binding + `clicked` signal, fill in `hourly_strip.py` with real data,
wire `AppState.location_changed`.

**Verification**: All 3 cards show plausible temps. Tap each → right column changes.
Clock unaffected. Sun/moon arc inside the dial updates to active location.

**Estimated context**: ~50k.

### Phase 3 — Radar (small + fullscreen)

**Deliverable**: Small radar widget under location cards loops the rainviewer
animation with colored border (green/white/amber). Tap → fullscreen with
timestamp. Tap fullscreen → back. Switching active location refetches.

**Files**: `radar/rainviewer.py`, `radar/basemap.py`, `radar/compositor.py`,
`ui/radar_widget.py`, `ui/radar_fullscreen.py`, add the `QStackedWidget` page
swap in `main.py`.

**Verification**: Visible rain (if any), animation visible, border color changes
as frame advances. Tap to fullscreen works. Tap each location card → radar
recenters within a few seconds.

**Estimated context**: ~60k. Largest phase. May need its own session.

### Phase 4 — Polish + deploy + cutover

**Deliverable**: `deploy.sh` script, `piclock2.desktop` autostart entry,
README with config docs. Old PiClock disabled, new one starts on boot.

**Files**: `deploy.sh`, `piclock2.desktop`, README updates.

**Verification**: Reboot the Pi; new app starts in fullscreen on the HDMI display.
RoomWizard VNC client and iPad VNC client both render acceptably (Lanczos
scaling on the RoomWizard side handles the rest).

**Estimated context**: ~20k.

## Critical Reuse from Existing Code

- `suntimes` class — port [PyQtPiClock.py:37-142](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L37-L142): change `print` → `print()`, change `offset.seconds / 3600.0` and similar to use float division (already float — no change needed actually), no other changes.
- `moon_phase()` function — port [PyQtPiClock.py:146-152](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L146-L152) verbatim.
- `phase()` function — port [PyQtPiClock.py:335-355](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L335-L355) (maps moon phase float to Lmoon1..Lmoon8 strings — keep our own English-only version, drop Config.Lmoon*).
- [GoogleMercatorProjection.py](c:/work/repos/PiClock/Clock/GoogleMercatorProjection.py) — copy as-is.
- Mapbox URL builder — port [PyQtPiClock.py:1841-1855](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L1841-L1855).
- Tile composition logic — port [PyQtPiClock.py:1786-1828](c:/work/repos/PiClock/Clock/PyQtPiClock.py#L1786-L1828).
- Artwork: `Clock/images/clockbackground-kevin.png`, `clockface3.png`, `hourhand.png`, `minhand.png`, `sechand.png`, and the `icons-lightblue/` directory. Symlink rather than copy so updates flow.

## What NOT to Touch

- The existing [Clock/](c:/work/repos/PiClock/Clock/) directory and [PyQtPiClock.py](c:/work/repos/PiClock/Clock/PyQtPiClock.py) — leave running until Phase 4 cutover.
- The deployed `/home/pi/PiClock/` — touch only via the `piclock2/` parallel install at `/home/pi/piclock2/`.
- `ApiKeys.py` — new app uses `config.toml` exclusively.
- The optional sidecar services (Temperature, Leds, Button, IR) — user explicitly opted out.

## Pre-flight Checks (do at the start of Phase 1)

```bash
ssh pi@192.168.50.56 '
  python3 --version &&
  python3 -c "import PyQt5.QtWidgets, PyQt5.QtGui, PyQt5.QtCore" 2>&1 &&
  python3 -c "import requests" 2>&1 &&
  python3 -c "import tomli" 2>&1
'
```

If any fail: `sudo apt install -y python3-pyqt5 python3-requests python3-tomli`.
(`python3-tomli` may not exist on Buster — fall back to `pip3 install tomli`.)

## Verification (end-to-end)

After Phase 4:

1. **Cold reboot**: `ssh pi@192.168.50.56 sudo reboot`. After 60 s, new app is visible on HDMI and via VNC.
2. **Radar overlay present**: small radar in lower-left shows rain (or visibly empty land for clear weather), border color cycles through frames.
3. **Hourly cadence**: right column shows 12 cards with 1-hour deltas (now, +1h, +2h, …).
4. **Multi-location**: tap Long Branch card → all "active" widgets update. Tap Budapest → metric units, Hungarian-language-friendly placeholder text (we keep English, but units flip).
5. **Fullscreen radar**: tap small radar → expands; timestamp overlay visible; tap → returns.
6. **Reliability**: leave running 24 h; no crashes, no memory growth, weather refreshes seen in logs every 30 min.

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Open-Meteo response format change | Fail-soft: log + keep last-good data; cards show last-known temp with a dim border |
| Rainviewer index unreachable | Same: dim the small radar border, show "—" timestamp on fullscreen |
| Drawing arc'd text in Qt is fiddly | Fallback: place date + sun/moon as straight text inside the dial (above and below center) if the arc looks bad |
| Buster Python 3.7 missing `tomli` | Fall back to `pip3 install --user tomli`; or replace with simple `configparser` if absolutely necessary |
| Mapbox quota | Existing key is already working on the old app; nothing changes in usage volume |
| Context budget exceeds 200k mid-phase | Each phase boundary is a commit; resume in fresh session by re-reading this plan file |

## Session Handoff Protocol

If we run out of context mid-implementation:
1. Last assistant message before exit should summarize: phase number, last completed step, next concrete action, any uncommitted changes.
2. New session starts with: `Read C:\Users\z001x91h\.claude\plans\wise-puzzling-quasar.md` + `git -C c:/work/repos/PiClock status` + `ls c:/work/repos/PiClock/piclock2/`.
3. Continue from the documented next action.
