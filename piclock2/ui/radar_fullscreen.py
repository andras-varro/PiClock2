"""
Expanded radar — a "lightbox" overlay.

Covers the whole window with a semi-transparent dim (so the main screen shows
faintly behind), and draws the current radar frame in a large centered panel
(~88% of the window, 16:9) with a thick age-colored border and a timestamp /
relative-age caption. It reads frames straight from the small RadarWidget (no
second fetch). Click anywhere to dismiss.
"""

import datetime

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from ui.radar_widget import BORDER_COLORS, RENDER_W, RENDER_H, frame_age_label

PANEL_FRACTION = 0.88        # of the window's shorter-constrained dimension
ASPECT = RENDER_W / float(RENDER_H)


class RadarOverlay(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.source = source       # the small RadarWidget
        self.setCursor(Qt.PointingHandCursor)
        self._scaled = {}          # (id(image), w, h) -> scaled QImage
        source.frame_changed.connect(self._on_frame_changed)

    def _on_frame_changed(self):
        if self.isVisible():
            self.update()

    def resizeEvent(self, evt):
        # Panel size changed -> previously scaled frames are the wrong size.
        self._scaled.clear()
        super().resizeEvent(evt)

    def _scaled_image(self, image, size):
        """Scale a frame to the panel once and cache it.

        Without this the full 1024x576 frame is SmoothTransformation-scaled to
        the big panel on every animation tick — heavy on a Pi 3, and over VNC
        it reads as sluggish, re-rendering-from-scratch drawing.
        """
        key = (id(image), size.width(), size.height())
        s = self._scaled.get(key)
        if s is None:
            if len(self._scaled) > 64:    # bound: only ~9 frames cycle at once
                self._scaled.clear()
            s = image.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._scaled[key] = s
        return s

    def _panel_rect(self):
        """Largest 16:9 rect fitting in PANEL_FRACTION of the window, centered."""
        w, h = self.width(), self.height()
        pw, ph = int(w * PANEL_FRACTION), int(h * PANEL_FRACTION)
        if pw / float(ph) > ASPECT:
            pw = int(ph * ASPECT)
        else:
            ph = int(pw / ASPECT)
        return QRect((w - pw) // 2, (h - ph) // 2, pw, ph)

    def _caption(self, frame):
        if frame.kind == "base":
            return "map · loading radar…"
        when = datetime.datetime.fromtimestamp(frame.time)
        stamp = when.strftime("%Y-%m-%d %H:%M")
        age = frame_age_label(self.source.frames, frame)
        kind = {"past": "observed", "now": "latest",
                "nowcast": "forecast"}.get(frame.kind, "")
        return "%s  ·  %s  ·  %s" % (age, stamp, kind)

    def paintEvent(self, _evt):
        p = QPainter(self)
        # Dim backdrop — main screen shows faintly through.
        p.fillRect(self.rect(), QColor(0, 0, 0, 160))

        panel = self._panel_rect()
        frame = self.source.current_frame()

        # Panel backing (in case a frame is missing or has transparency).
        p.fillRect(panel, QColor(8, 12, 18))

        if frame is None:
            p.setPen(QColor(190, 238, 255, 160))
            p.setFont(QFont("Arial", 20))
            p.drawText(panel, Qt.AlignCenter, "radar loading…")
            border = QColor(190, 238, 255, 120)
        else:
            scaled = self._scaled_image(frame.image, panel.size())
            x = panel.x() + (panel.width() - scaled.width()) // 2
            y = panel.y() + (panel.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)
            border = BORDER_COLORS.get(frame.kind, QColor("#ffffff"))

            # Caption, top-left inside the panel.
            text = self._caption(frame)
            p.setFont(QFont("Arial", 18, QFont.Bold))
            tx, ty = panel.x() + 22, panel.y() + 38
            p.setPen(QColor(0, 0, 0, 210))
            p.drawText(tx + 1, ty + 1, text)
            p.setPen(border)
            p.drawText(tx, ty, text)

        pen = QPen(border)
        pen.setWidth(6)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(panel.adjusted(3, 3, -3, -3))
        p.end()

    def mousePressEvent(self, _evt):
        self.dismissed.emit()
