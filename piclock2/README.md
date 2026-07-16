# PiClock 2

A from-scratch rewrite of [n0bel/PiClock](../README.md), aimed at:

- **Python 3 + PyQt5** (apt-installable on Buster, easy port to Qt6 later)
- **Working radar** via rainviewer's current API
- **True hourly forecast** via Open-Meteo (no API key, no rate-limit worries)
- **Multi-location**: a column of location cards; tap to switch active location
- **Compact layout** suitable for VNC viewers (RoomWizard 800×480, iPad)

See [PLAN.md](PLAN.md) for the full design and implementation phases.

## Phase 1 (current)

Skeleton with:
- Centered analog clock with date arc'd inside top of dial and sun/moon arc'd inside bottom.
- Left column of (currently placeholder) location cards.
- Right column of (currently placeholder) hourly forecast rows.
- Phase 2 will hook up Open-Meteo. Phase 3 will hook up rainviewer.

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
│  Location card  │                          │  now      ...    │
│  Location card  │      BIG ANALOG          │  +1h      ...    │
│  Location card  │       CLOCK              │  +2h      ...    │
│                 │   ◜ date arc top ◝       │  +3h      ...    │
│                 │   ◟ sun/moon bot ◞       │  ...             │
│ ┌─────────────┐ │                          │  +11h     ...    │
│ │  RADAR      │ │                          │                  │
│ │  280×280    │ │                          │                  │
│ └─────────────┘ │                          │                  │
└─────────────────┴──────────────────────────┴──────────────────┘
```

## License

Same as the parent project (MIT-style; see [../LICENSE](../LICENSE)).
Clock face and hand artwork from [n0bel/PiClock](../README.md) by Kevin Uhlir.
