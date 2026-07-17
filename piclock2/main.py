#!/usr/bin/env python3
"""
PiClock 2 — main entry point.

Phase 1 layout:
    [ left column ] [ centered clock ] [ right hourly strip ]

Run with:
    python3 main.py
Optional:
    PICLOCK2_CONFIG=/path/to/config.toml python3 main.py
"""

import os
import sys
import time
import signal

from PyQt5.QtCore import Qt, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QPixmap, QBrush, QPainter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from config import load_default
from app_state import AppState
from ui.location_column import LocationColumn
from ui.clock_face import ClockFace
from ui.forecast_panel import ForecastPanel
from ui.radar_fullscreen import RadarOverlay
from ui.alert_banner import AlertBanner
from ui.alert_overlay import AlertOverlay
from weather.open_meteo import fetch as fetch_weather
from weather.air_quality import fetch_air_quality
from weather.alerts import fetch_alerts


ASSETS_DIR = os.path.join(HERE, "assets")

WEATHER_REFRESH_MINUTES = 30
# Open-Meteo occasionally times out from the Pi. Rather than leave a location
# blank until the next 30-min cycle, retry a failed fetch a few times soon after.
WEATHER_RETRY_MS = 45 * 1000
WEATHER_MAX_RETRIES = 4


class _WorkerSignals(QObject):
    weather = pyqtSignal(int, object, object, object, float)  # index, current, hourly, daily, when
    alerts = pyqtSignal(int, object)                   # index, [WeatherAlert]
    failed = pyqtSignal(int, str)
    finished = pyqtSignal(object)                      # the worker itself


class WeatherWorker(QRunnable):
    """Fetch one location's weather (+ air quality + alerts) off the GUI thread."""

    def __init__(self, index, location, owm_key=""):
        super().__init__()
        self.index = index
        self.location = location
        self.owm_key = owm_key
        self.signals = _WorkerSignals()
        self.setAutoDelete(False)

    def run(self):
        try:
            current, hourly, daily = fetch_weather(self.location)
            # Air quality is best-effort and merged in before we emit, so the
            # UI models arrive AQI-complete. A slow/failed AQI API must never
            # blank the weather or kill the worker.
            try:
                aq = fetch_air_quality(self.location)
                _merge_air_quality(current, hourly, daily, aq)
            except Exception:  # noqa: BLE001
                pass
            # Emit weather first so display latency is unchanged by alerts.
            self.signals.weather.emit(
                self.index, current, hourly, daily, time.time())
            try:
                alerts = fetch_alerts(self.location, self.owm_key)
            except Exception:  # noqa: BLE001
                alerts = []
            self.signals.alerts.emit(self.index, alerts)
        except Exception as e:  # noqa: BLE001 - fail-soft, keep last-good data
            self.signals.failed.emit(self.index, repr(e))
        finally:
            self.signals.finished.emit(self)


def _merge_air_quality(current, hourly, daily, aq):
    """Stitch AQI (both scales) into the weather models by timestamp/date."""
    if current is not None:
        current.aqi_us = aq.current.get("us")
        current.aqi_eu = aq.current.get("eu")
    for h in hourly:
        v = aq.hourly.get(h.time_iso)
        if v:
            h.aqi_us = v.get("us")
            h.aqi_eu = v.get("eu")
    for d in daily:
        v = aq.daily.get(d.date)   # None for days beyond the AQI horizon (~7)
        if v:
            d.aqi_us = v.get("us")
            d.aqi_eu = v.get("eu")


class WeatherService(QObject):
    """Refreshes every location's weather on a timer via a thread pool."""

    def __init__(self, app_state, owm_key="", refresh_minutes=WEATHER_REFRESH_MINUTES,
                 parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.owm_key = owm_key
        self.pool = QThreadPool.globalInstance()
        self._workers = []
        self._retries = {}              # location index -> attempts so far
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self._refresh_ms = int(refresh_minutes * 60 * 1000)

    def start(self):
        self.refresh_all()
        self.timer.start(self._refresh_ms)

    def refresh_all(self):
        self._retries.clear()           # fresh cycle resets the retry budget
        for i, ld in enumerate(self.app_state.data):
            self._spawn(i, ld.location)

    def _spawn(self, i, location):
        w = WeatherWorker(i, location, self.owm_key)
        w.signals.weather.connect(self._on_weather)
        w.signals.alerts.connect(self._on_alerts)
        w.signals.failed.connect(self._on_failed)
        w.signals.finished.connect(self._retire)
        self._workers.append(w)
        self.pool.start(w)

    def _on_weather(self, i, current, hourly, daily, when):
        self._retries.pop(i, None)
        self.app_state.update_weather(i, current, hourly, daily, when)

    def _on_alerts(self, i, alerts):
        self.app_state.update_alerts(i, alerts)

    def _on_failed(self, i, msg):
        name = self.app_state.data[i].location.name
        n = self._retries.get(i, 0) + 1
        self._retries[i] = n
        if n <= WEATHER_MAX_RETRIES:
            print("piclock2: weather fetch failed for", name, "- retry",
                  n, "in", WEATHER_RETRY_MS // 1000, "s -", msg, file=sys.stderr)
            loc = self.app_state.data[i].location
            QTimer.singleShot(WEATHER_RETRY_MS, lambda: self._spawn(i, loc))
        else:
            print("piclock2: weather fetch failed for", name,
                  "- giving up until next cycle -", msg, file=sys.stderr)

    def _retire(self, w):
        try:
            self._workers.remove(w)
        except ValueError:
            pass


class MainPage(QWidget):
    """Three-column layout: locations | clock | hourly."""

    def __init__(self, cfg, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state

        self.location_column = LocationColumn(app_state, cfg, parent=self)
        self.clock = ClockFace(ASSETS_DIR, app_state, parent=self)
        self.forecast = ForecastPanel(app_state, parent=self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.location_column, 0)
        layout.addWidget(self.clock, 1)
        layout.addWidget(self.forecast, 0)

        # Fixed column widths; clock takes the rest. Sized for a 1920-wide
        # canvas, with large fonts for the RoomWizard VNC downscale.
        self.location_column.setFixedWidth(420)
        self.forecast.setFixedWidth(470)


class MainWindow(QWidget):
    def __init__(self, cfg, app_state):
        super().__init__()
        self.cfg = cfg
        self.app_state = app_state
        self.setWindowTitle("PiClock 2")

        # Background: scaled-to-cover, painted in paintEvent (QSS has no
        # background-size). Cache the scaled pixmap per window size.
        bg_path = os.path.join(ASSETS_DIR, "images", "clockbackground-kevin.png")
        self._bg_src = QPixmap(bg_path) if os.path.isfile(bg_path) else QPixmap()
        self._bg_scaled = QPixmap()
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#000000"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        # The single page fills the window via a margin-free layout.
        self.main_page = MainPage(cfg, app_state, parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_page)

        # Expanded radar lightbox: a free-floating child raised over the page.
        self.radar_overlay = RadarOverlay(self.main_page.location_column.radar,
                                          parent=self)
        self.radar_overlay.hide()

        self.main_page.location_column.radar_clicked.connect(self._show_radar)
        self.radar_overlay.dismissed.connect(self._hide_radar)

        # Weather alerts: a top banner for the active location (auto-hides when
        # there are none) and a click-through detail lightbox.
        self.alert_banner = AlertBanner(app_state, parent=self)
        self.alert_overlay = AlertOverlay(app_state, parent=self)
        self.alert_overlay.hide()
        self.alert_banner.clicked.connect(self._show_alerts)
        self.alert_overlay.dismissed.connect(self._hide_alerts)
        self.alert_banner.shown_changed.connect(self._layout_banner)

    def _layout_banner(self):
        # Span the center clock area only (between the side columns) so the
        # banner never covers the location cards or the hourly strip.
        lc = self.main_page.location_column.width() or 420
        hr = self.main_page.forecast.width() or 470
        w = max(240, self.width() - lc - hr)
        self.alert_banner.setGeometry(lc, 0, w, self.alert_banner.height())
        self.alert_banner.raise_()

    def _show_alerts(self):
        self.alert_overlay.setGeometry(self.rect())
        self.alert_overlay.populate()
        self.alert_overlay.show()
        self.alert_overlay.raise_()

    def _hide_alerts(self):
        self.alert_overlay.hide()

    def _show_radar(self):
        self.radar_overlay.setGeometry(self.rect())
        self.radar_overlay.show()
        self.radar_overlay.raise_()

    def _hide_radar(self):
        self.radar_overlay.hide()

    def resizeEvent(self, evt):
        if not self._bg_src.isNull():
            self._bg_scaled = self._bg_src.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation)
        if self.radar_overlay.isVisible():
            self.radar_overlay.setGeometry(self.rect())
        if self.alert_overlay.isVisible():
            self.alert_overlay.setGeometry(self.rect())
        self._layout_banner()
        super().resizeEvent(evt)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        if not self._bg_scaled.isNull():
            # Center the cover-scaled pixmap (it may overflow one axis).
            x = (self.width() - self._bg_scaled.width()) // 2
            y = (self.height() - self._bg_scaled.height()) // 2
            p.drawPixmap(x, y, self._bg_scaled)
        p.end()

    def keyPressEvent(self, evt):
        key = evt.key()
        if key == Qt.Key_Escape and self.alert_overlay.isVisible():
            self._hide_alerts()
            return
        if key == Qt.Key_Escape and self.radar_overlay.isVisible():
            self._hide_radar()
            return
        if key == Qt.Key_F4 or key == Qt.Key_Escape:
            QApplication.instance().quit()
            return
        super().keyPressEvent(evt)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    cfg = load_default()
    state = AppState(cfg.locations)

    win = MainWindow(cfg, state)
    if cfg.fullscreen:
        win.showFullScreen()
    else:
        win.resize(cfg.width, cfg.height)
        win.show()

    weather = WeatherService(state, owm_key=cfg.owm_key)
    weather.start()

    win.main_page.location_column.radar.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
