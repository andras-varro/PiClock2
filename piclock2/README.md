# PiClock 2

A from-scratch rewrite of [n0bel/PiClock](../README.md), aimed at:

- **Python 3 + PyQt5** (apt-installable on Buster, easy port to Qt6 later)
- **Working radar** via rainviewer's current API
- **True hourly forecast** via Open-Meteo (no API key, no rate-limit worries)
- **10-day daily forecast** and **Air Quality (AQI)**, also from Open-Meteo
- **Multi-location**: a column of location cards; tap to switch active location
- **Weather alerts**: keyless NWS (US) + optional OpenWeatherMap (non-US)
- **Compact layout** suitable for VNC viewers (RoomWizard 800×480, iPad)

See [PLAN.md](PLAN.md) for the full design and implementation phases.

## Features

- Centered analog clock with the date arc'd inside the top of the dial and
  sun/moon arc'd inside the bottom, for the active location.
- Left column: location cards (active one shows feels-like, humidity, wind, and
  AQI) and a live radar below.
- Right column: a **Hourly | 10-Day** tabbed forecast. Hourly starts at the
  **next** hour; both views show AQI as a colored dot + number.
- AQI scale is per-region: **US AQI** for imperial locations, **European AQI**
  for metric ones (override with `aqi_scale` per location). AQI only forecasts
  ~7 days, so the last few 10-day rows show no AQI.

## Install (Raspberry Pi Buster)

```bash
sudo apt install -y python3-pyqt5 python3-requests python3-toml python3-dateutil python3-tzlocal
```

## Configure

Copy `config.example.toml` to `config.toml` (in the same dir, or `~/.config/piclock2/`)
and edit the locations / Mapbox key.

```bash
cp config.example.toml config.toml
$EDITOR config.toml
```

`config.toml` is loaded from (first hit wins):

1. `$PICLOCK2_CONFIG`
2. `./config.toml`
3. `~/.config/piclock2/config.toml`
4. `./config.example.toml` (fallback so the app at least starts)

## Run

```bash
python3 main.py
```

Press **F4** or **Escape** to quit.

Set `fullscreen = true` in `config.toml` for the Pi; keep `false` on a desktop.

## Layout

```
┌─────────────────┬──────────────────────────┬──────────────────┐
│  Location card  │                          │ [Hourly] 10-Day  │
│  Location card  │      BIG ANALOG          │  +1h  ● ...      │
│  Location card  │       CLOCK              │  +2h  ● ...      │
│  (active: AQI)  │   ◜ date arc top ◝       │  +3h  ● ...      │
│                 │   ◟ sun/moon bot ◞       │  ...             │
│ ┌─────────────┐ │                          │  +12h ● ...      │
│ │  RADAR      │ │                          │  (tap 10-Day for │
│ │  280×280    │ │                          │   the daily view)│
│ └─────────────┘ │                          │                  │
└─────────────────┴──────────────────────────┴──────────────────┘
```

## Deploy to the Pi

`deploy.sh` rsyncs the working tree to the Pi (excluding `config.toml`, logs,
caches, and dev scratch), so your on-device `config.toml` (with the Mapbox key)
is never overwritten:

```bash
./deploy.sh                       # defaults to pi@192.168.50.56:/home/pi/piclock2
./deploy.sh pi@otherhost:/path    # override target
```

## Autostart on boot

Install `piclock2.desktop` into the Pi's autostart directory so the LXDE
session launches the clock via `startup.sh`:

```bash
mkdir -p ~/.config/autostart
cp ~/piclock2/piclock2.desktop ~/.config/autostart/piclock2.desktop
```

To cut over from the old Python-2 PiClock, remove its autostart entry
(`~/.config/autostart/PiClock.desktop`) so only piclock2 starts, then reboot.

## License

Same as the parent project (MIT-style; see [../LICENSE](../LICENSE)).
Clock face and hand artwork from [n0bel/PiClock](../README.md) by Kevin Uhlir.
