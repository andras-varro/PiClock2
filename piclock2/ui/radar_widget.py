"""
Small always-on radar widget (~280x280) under the location cards.

Owns the radar data pipeline: a RadarWorker(QRunnable) fetches the rainviewer
index + Mapbox basemap + per-frame tiles off the GUI thread (requests), and
build_frame() composites each frame into a QImage. The widget loops the frames
on a QTimer, drawing a border colored by frame age:

    green  = past observation
    white  = most recent observation ("now")
    amber  = nowcast (future)

Refetches when the active location changes and on a periodic timer. The
fullscreen view reads frames straight from this widget (see RadarFullscreen).
"""

import sys
import time
from dataclasses import dataclass

import requests
from PyQt5.QtCore import (
    Qt, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from radar import basemap, rainviewer
from radar.compositor import RadarGeometry, build_frame

# Working resolution we composite at. A 16:9 frame so the expanded lightbox
# fills a wide panel without letterboxing; the small widget crops to its box.
RENDER_W = 1024
RENDER_H = 576
PAST_FRAMES = 6
# rainviewer only generates radar tiles up to zoom 7; zoom 8+ returns a
# "Zoom Level Not Supported" placeholder tile. Cap the effective zoom (for both
# the tiles and the Mapbox basemap, so they stay geographically aligned).
MAX_RAINVIEWER_ZOOM = 7
RADAR_REFRESH_MS = 5 * 60 * 1000     # global refetch cadence
# Flipping between locations should be instant, not a full re-download. Each
# location's composited frames are cached this long; a switch back within the
# window reuses them, older than this triggers a fresh fetch.
RADAR_CACHE_TTL_S = RADAR_REFRESH_MS / 1000.0
FRAME_MS = 300                       # animation step
HOLD_TICKS = 6                       # extra ticks to pause on the "now" frame

BORDER_COLORS = {
    "base": QColor("#50CBEB"),       # map-only placeholder (before tiles land)
    "past": QColor("#2ecc71"),
    "now": QColor("#ffffff"),
    "nowcast": QColor("#ffbf00"),
}


def frame_age_label(frames, frame):
    """Short relative-age label for `frame` vs the 'now' frame.

    Returns "now", "+10m" (nowcast/future) or "-30m" (past). Used by both the
    small widget and the expanded overlay so they read consistently.
    """
    if frame is None:
        return ""
    now_t = next((f.time for f in frames if f.kind == "now"), None)
    if now_t is None or frame.time == now_t:
        return "now"
    delta = int(frame.time - now_t)
    return "%s%dm" % ("+" if delta > 0 else "-", abs(delta) // 60)


@dataclass
class RenderedFrame:
    time: int
    kind: str
    image: QImage


class _WorkerSignals(QObject):
    base = pyqtSignal(int, object)    # location index, base QImage (map only)
    frame = pyqtSignal(int, object)   # location index, one RenderedFrame
    done = pyqtSignal(int, int)       # location index, frame count
    failed = pyqtSignal(int, str)
    finished = pyqtSignal(object)     # the worker itself


class RadarWorker(QRunnable):
    """Fetch + composite radar frames for one location off the GUI thread.

    Emits progressively so the UI feels responsive on a location switch:
      1. `base`  as soon as the Mapbox basemap is fetched (map shows in ~1-2s),
      2. `frame` for each radar frame as it finishes compositing (clouds fill
         in and start animating instead of waiting for the whole batch),
      3. `done`  once every frame has been emitted.
    """

    def __init__(self, index, location, mapbox_key, mapbox_style):
        super().__init__()
        self.index = index
        self.location = location
        self.mapbox_key = mapbox_key
        self.mapbox_style = mapbox_style
        self.signals = _WorkerSignals()
        self.setAutoDelete(False)

    def _get_image(self, session, url, timeout=10):
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        img = QImage()
        img.loadFromData(resp.content)
        return img

    def run(self):
        try:
            loc = self.location
            session = requests.Session()    # keep-alive: tiles share one host
            zoom = min(loc.radar_zoom, MAX_RAINVIEWER_ZOOM)
            geom = RadarGeometry(loc.lat, loc.lng, zoom,
                                 RENDER_W, RENDER_H)

            url = basemap.mapbox_url(loc.lat, loc.lng, zoom,
                                     RENDER_W, RENDER_H,
                                     self.mapbox_style, self.mapbox_key)
            base = self._get_image(session, url)
            if base.isNull():
                raise RuntimeError("basemap fetch returned no image")
            if base.size().width() != RENDER_W or base.size().height() != RENDER_H:
                base = base.scaled(RENDER_W, RENDER_H,
                                   Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            # Show the map straight away, before any radar tiles are fetched.
            self.signals.base.emit(self.index, base)

            idx = rainviewer.fetch_index()
            host, frames = rainviewer.select_frames(idx, PAST_FRAMES)

            count = 0
            for fr in frames:
                tiles = []
                for (x, y) in geom.tiles:
                    turl = rainviewer.tile_url(host, fr.path, geom.zoom, x, y)
                    try:
                        tiles.append(self._get_image(session, turl))
                    except Exception:
                        tiles.append(None)
                img = build_frame(base, tiles, geom)
                self.signals.frame.emit(
                    self.index,
                    RenderedFrame(time=fr.time, kind=fr.kind, image=img))
                count += 1

            self.signals.done.emit(self.index, count)
        except Exception as e:  # noqa: BLE001 - fail-soft, keep last-good frames
            self.signals.failed.emit(self.index, repr(e))
        finally:
            self.signals.finished.emit(self)


class RadarWidget(QWidget):
    """Small looping radar with an age-colored border. Click toggles fullscreen."""

    clicked = pyqtSignal()
    frame_changed = pyqtSignal()       # current frame advanced (drives fullscreen)

    def __init__(self, app_state, cfg, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.cfg = cfg
        self.setMinimumSize(260, 260)
        self.setCursor(Qt.PointingHandCursor)

        self.frames = []
        self.displayed = 0
        self._hold = 0
        self._loading_index = -1     # location whose frames are mid-fetch
        self._scaled = {}            # (id(image), w, h) -> pre-scaled QPixmap
        self._cache = {}             # loc index -> (fetched_at, [RenderedFrame])
        self._accum = {}             # loc index -> frames accumulating mid-fetch
        self._workers = []
        self._pool = QThreadPool.globalInstance()

        self.anim = QTimer(self)
        self.anim.timeout.connect(self._advance)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(lambda: self.refresh(force=True))

        app_state.location_changed.connect(lambda _i: self.refresh())

    def start(self):
        self.refresh()
        self.refresh_timer.start(RADAR_REFRESH_MS)
        self.anim.start(FRAME_MS)

    # ---- data ----------------------------------------------------------

    def refresh(self, force=False):
        idx = self.app_state.active_index
        loc = self.app_state.active.location
        # Serve recently-fetched frames from cache so flipping back to a
        # location is instant instead of re-downloading every tile. The
        # periodic timer passes force=True to keep the live location current.
        if not force:
            entry = self._cache.get(idx)
            if entry is not None:
                fetched_at, frames = entry
                if frames and (time.time() - fetched_at) < RADAR_CACHE_TTL_S:
                    self._show_frames(frames)
                    self._loading_index = -1
                    return
        self._loading_index = idx
        self._accum[idx] = []        # real frames accumulate here until done
        w = RadarWorker(idx, loc, self.cfg.mapbox_key, self.cfg.mapbox_style)
        w.signals.base.connect(self._on_base)
        w.signals.frame.connect(self._on_frame)
        w.signals.done.connect(self._on_done)
        w.signals.failed.connect(self._on_failed)
        w.signals.finished.connect(self._retire)
        self._workers.append(w)
        self._pool.start(w)

    def _show_frames(self, frames):
        """Display an already-composited frame set (from cache)."""
        self.frames = list(frames)
        self.displayed = 0
        self._hold = 0
        self._scaled.clear()
        self.frame_changed.emit()
        self.update()

    def _on_base(self, index, base_image):
        # Map only — show it immediately so a location switch feels instant.
        if index != self.app_state.active_index:
            return
        self.frames = [RenderedFrame(time=0, kind="base", image=base_image)]
        self.displayed = 0
        self._hold = 0
        self._scaled.clear()
        self.frame_changed.emit()
        self.update()

    def _on_frame(self, index, rendered):
        # Each composited radar frame, as it becomes available. Accumulate for
        # every location (so a background fetch still fills the cache), but only
        # repaint when it's the one on screen.
        self._accum.setdefault(index, []).append(rendered)
        if index != self.app_state.active_index:
            return
        # The first real frame replaces the map-only placeholder.
        if len(self.frames) == 1 and self.frames[0].kind == "base":
            self.frames = []
            self.displayed = 0
        self.frames.append(rendered)
        self.frame_changed.emit()
        self.update()

    def _on_done(self, index, count):
        acc = self._accum.pop(index, [])
        if acc:
            self._cache[index] = (time.time(), acc)
        if index != self.app_state.active_index:
            return
        self._loading_index = -1

    def _on_failed(self, index, msg):
        print("piclock2: radar fetch failed -", msg, file=sys.stderr)

    def _retire(self, w):
        try:
            self._workers.remove(w)
        except ValueError:
            pass

    # ---- animation -----------------------------------------------------

    def _advance(self):
        if len(self.frames) < 2:
            return
        # Pause a few ticks on the freshest ("now") frame for legibility.
        if self.frames[self.displayed].kind == "now" and self._hold < HOLD_TICKS:
            self._hold += 1
            return
        self._hold = 0
        self.displayed = (self.displayed + 1) % len(self.frames)
        self.frame_changed.emit()
        self.update()

    def current_frame(self):
        if 0 <= self.displayed < len(self.frames):
            return self.frames[self.displayed]
        return None

    # ---- paint / input -------------------------------------------------

    def _scaled_pixmap(self, frame, size):
        """Cover-scale a frame to `size` once and cache it (keyed by image id).

        Re-scaling the 1024x576 source on every animation tick is the single
        biggest paint cost; caching turns each tick into a plain blit, which
        matters a lot when x11vnc is also using the CPU.
        """
        key = (id(frame.image), size.width(), size.height())
        pix = self._scaled.get(key)
        if pix is None:
            scaled = frame.image.scaled(size, Qt.KeepAspectRatioByExpanding,
                                        Qt.SmoothTransformation)
            x = (scaled.width() - size.width()) // 2
            y = (scaled.height() - size.height()) // 2
            pix = QPixmap.fromImage(
                scaled.copy(x, y, size.width(), size.height()))
            self._scaled[key] = pix
        return pix

    def resizeEvent(self, evt):
        self._scaled.clear()
        super().resizeEvent(evt)

    def paintEvent(self, _evt):
        p = QPainter(self)
        rect = self.rect()
        frame = self.current_frame()
        if frame is not None:
            p.drawPixmap(rect, self._scaled_pixmap(frame, rect.size()))
            color = BORDER_COLORS.get(frame.kind, QColor("#888888"))
        else:
            p.fillRect(rect, QColor(255, 255, 255, 20))
            p.setPen(QColor(190, 238, 255, 160))
            p.drawText(rect, Qt.AlignCenter, "radar\nloading…")
            color = QColor(190, 238, 255, 90)

        pen = QPen(color)
        pen.setWidth(4)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect.adjusted(2, 2, -2, -2))

        # Small age label, bottom-left, so a nowcast (amber) frame is obvious.
        if frame is not None:
            label = "map" if frame.kind == "base" else \
                frame_age_label(self.frames, frame)
            p.setFont(QFont("Arial", 12, QFont.Bold))
            lx, ly = 10, rect.height() - 10
            p.setPen(QColor(0, 0, 0, 200))
            p.drawText(lx + 1, ly + 1, label)
            p.setPen(color)
            p.drawText(lx, ly, label)
        p.end()

    def mousePressEvent(self, _evt):
        self.clicked.emit()
