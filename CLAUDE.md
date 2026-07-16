# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Runtime

- **Python 2** only (not 3). All `*.py` files use `print foo` statement syntax, `except Exception, e:`, integer division, etc. Do not "modernize" to Python 3 — `update.py`, `startup.sh`, and every module assume the system `python` is 2.7+.
- **PyQt4** (not PyQt5). On Raspbian this is the `python-qt4` apt package; there is no `requirements.txt` / `pip install` path that produces a working environment by itself.
- **Target platform**: Raspberry Pi running Raspbian (Stretch-era), running X11 with the app fullscreen. The Windows/Mac/Linux desktop path is supported but secondary (see [Documentation/Install-Clock-Only.md](Documentation/Install-Clock-Only.md)).

## Running it

The clock is one program: `Clock/PyQtPiClock.py`. There is no build, no test suite, no lint config.

```
cd Clock
python PyQtPiClock.py            # uses Config.py
python PyQtPiClock.py Config-Night   # uses Config-Night.py
```

The argv handling at [Clock/PyQtPiClock.py:2053-2062](Clock/PyQtPiClock.py#L2053-L2062) does `Config = __import__(sys.argv[1] or 'Config')` — this is how [switcher.sh](switcher.sh) flips skins on a cron schedule (e.g. day/night configs).

On a Pi, `startup.sh` is the real entry point — it waits for X, disables screen blanking, conditionally launches the optional companion services (see below) if their dependencies import, and finally `cd Clock && python -u PyQtPiClock.py`, rotating logs `PyQtPiClock.[1-7].log` in `Clock/`.

## Required user-created files

Both live in `Clock/`, both are gitignored, both are required for the app to function. Copy from the examples and edit:

- `Clock/ApiKeys.py` ← `Clock/ApiKeys-example.py` — API keys for the chosen weather + map providers.
- `Clock/Config.py` ← one of `Clock/Config-Example*.py` — location, units, layout, radar definitions, language strings.

Provider selection is **driven by which keys are present in `ApiKeys.py`**, not by an explicit setting. The dispatcher at [Clock/PyQtPiClock.py:1372-1400](Clock/PyQtPiClock.py#L1372-L1400) (`getwx`) tries each provider in order via `try: ApiKeys.tmapi / except: pass` — `tmapi` (Tomorrow.io) wins over `owmapi` (OpenWeatherMap). Similarly `mbapi` starting with `pk.` flips `Config.usemapbox` on at [Clock/PyQtPiClock.py:2173-2178](Clock/PyQtPiClock.py#L2173-L2178). DarkSky is gone — `update.py` strips `dsapi`/`wuapi` from old `ApiKeys.py` files.

This `try/except AttributeError` pattern is the project-wide idiom for optional config — every new optional setting is also given a default in the long block at [Clock/PyQtPiClock.py:2066-2169](Clock/PyQtPiClock.py#L2066-L2169) so old `Config.py` files keep working.

## Architecture

**Single-file Qt event loop.** [Clock/PyQtPiClock.py](Clock/PyQtPiClock.py) (~2600 lines, mostly module-level code, not classes) drives everything from a `QApplication` with three `QTimer`s wired in `qtstart()` at [Clock/PyQtPiClock.py:1503](Clock/PyQtPiClock.py#L1503):

- `ctimer` — 1 Hz → `tick()` redraws clock hands / digital text, recomputes sunrise/sunset on day rollover.
- `wxtimer` — every `Config.weather_refresh` minutes → `getallwx()` → provider-specific `getwx_owm` / `getwx_tm` / `getwx_metar`.
- `temptimer` — every 10 min → `gettemp()` hits the local TempServer.

HTTP is async via a single `QtNetwork.QNetworkAccessManager` named `manager`. Each request gets its own `wxreply*` / `tilereply` global and a `.finished.connect(handler)` callback — never `requests`, never threads in the main app. This is why each weather provider has matching `getwx_xxx` / `wxfinished_xxx` halves.

**Pages.** UI is a list of `QFrame`s in `frames[]`, only one visible at a time. `nextframe(±1)` at [Clock/PyQtPiClock.py:2000](Clock/PyQtPiClock.py#L2000) cycles them. Keypress handling is in `myMain.keyPressEvent` at [Clock/PyQtPiClock.py:2015](Clock/PyQtPiClock.py#L2015): Space/←/→ change page, F2 toggles the `mpg123` NOAA stream subprocess, F4 quits, F6/F7/F8 control the optional slideshow, F9 toggles the foreground overlay.

**Radar.** Tiles come from rainviewer.com; the underlying map comes from Google Static Maps OR Mapbox. The `Radar` class around [Clock/PyQtPiClock.py:1633-1965](Clock/PyQtPiClock.py#L1633-L1965) computes the slippy-tile grid for the configured center+zoom (using `Clock/GoogleMercatorProjection.py`), fetches each rainviewer tile, composites them into a single `QImage`, then animates `Config.radar1..4` definitions cycle via `rtick`.

**Localization.** All user-facing strings live in `Config.py` as `L*` variables (`LPressure`, `LSunRise`, `Lmoon1..8`, `Lcc_code_map`, `Ltm_code_map`). To translate, change those — do not hardcode strings in `PyQtPiClock.py`. See `Config-Example-Berlin.py` / `Config-Example-London.py` for examples.

## Optional companion services

Each is independent, runs as its own process, and is only started by [startup.sh](startup.sh) if its dependency import succeeds — so missing hardware silently skips. The main clock talks to them only over local sockets / `uinput` keystrokes.

- **[Temperature/TempServer.py](Temperature/TempServer.py)** — Polls DS18B20 1-Wire sensors via `w1thermsensor`, serves the readings as JSON on `http://localhost:48213/`, also accepts UDP pushes from remote sensors on port 53535. `Clock/PyQtPiClock.py` `gettemp()` fetches from this URL — sensor IDs are mapped to human names in `Temperature/TempNames.py`.
- **[Leds/NeoAmbi.py](Leds/NeoAmbi.py)** — NeoPixel ambilight driver (rpi_ws281x). Must run as root because of `/dev/mem`.
- **[Button/](Button/)** — `gpio-keys.c` (built with `make gpio-keys`) maps GPIO pins to uinput keypresses; startup.sh runs it as `sudo Button/gpio-keys 23:KEY_SPACE 24:KEY_F2 25:KEY_UP`. The clock just sees normal key events.
- **IR remote** — Configured through Lirc + `IR/lircd.conf`, also delivers normal key events; no in-tree daemon.

## Updating

`python update.py` (run on the Pi after `git pull`) pip-upgrades runtime deps, fixes permissions on `Button/gpio-keys`, and migrates `Clock/ApiKeys.py` to remove obsolete keys / prompt for new ones. It is Python 2, uses `sudo pip`, and assumes a Raspbian environment — don't run it on a Windows dev box.
