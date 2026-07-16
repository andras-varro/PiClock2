"""
Alert detail lightbox.

Covers the window with a dim backdrop and shows the active location's alerts in
a centered, scrollable panel — one block per alert with a severity-colored
header, time window, sender, and the full wrapped description + instruction.
Mirrors the dim+panel pattern of radar_fullscreen.RadarOverlay. Click the dim
margin or press Esc to dismiss.
"""

import datetime

from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QLabel, QFrame, QVBoxLayout,
)

from models import severity_color, severity_text_color

PANEL_FRACTION = 0.86


class AlertOverlay(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setCursor(Qt.PointingHandCursor)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 12px; }"
            "QScrollBar::handle:vertical { background: rgba(190,238,255,120);"
            " border-radius: 6px; }"
        )
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(26, 26, 26, 26)
        self.vbox.setSpacing(16)
        self.scroll.setWidget(self.container)

        app_state.alerts_updated.connect(self._on_alerts_updated)

    def _on_alerts_updated(self, i):
        if self.isVisible() and i == self.app_state.active_index:
            self.populate()

    # ---- content -------------------------------------------------------

    def populate(self):
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        ld = self.app_state.active
        title = QLabel(ld.location.name + " — Weather Alerts")
        title.setStyleSheet(
            "color: #bef; font-size: 30px; font-weight: bold; background: transparent;")
        self.vbox.addWidget(title)

        alerts = ld.alerts
        if not alerts:
            none = QLabel("No active alerts for this location.")
            none.setStyleSheet(
                "color: #bef; font-size: 22px; background: transparent;")
            self.vbox.addWidget(none)
        else:
            for a in alerts:
                self.vbox.addWidget(self._alert_block(a))
        self.vbox.addStretch(1)

    def _alert_block(self, a):
        color = severity_color(a.severity)
        text_on = severity_text_color(a.severity)
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: rgba(0,0,0,150); border: 2px solid "
            + color + "; border-radius: 10px; }"
            "QLabel { background: transparent; }"
        )
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 12, 16, 14)
        box.setSpacing(6)

        header = QLabel(a.event)
        header.setStyleSheet(
            "color: %s; background-color: %s; border-radius: 6px;"
            " padding: 3px 10px; font-size: 26px; font-weight: bold;"
            % (text_on, color))
        box.addWidget(header)

        meta_bits = []
        window = self._fmt_window(a)
        if window:
            meta_bits.append(window)
        if a.severity and a.severity != "Unknown":
            meta_bits.append(a.severity)
        if a.sender:
            meta_bits.append(a.sender)
        if meta_bits:
            meta = QLabel("   ·   ".join(meta_bits))
            meta.setStyleSheet("color: #9fd6ef; font-size: 18px;")
            box.addWidget(meta)

        body_text = a.description or a.headline or ""
        if a.instruction:
            body_text = (body_text + "\n\n" + a.instruction).strip()
        if body_text:
            body = QLabel(body_text)
            body.setWordWrap(True)
            body.setStyleSheet("color: #e6f6ff; font-size: 19px;")
            box.addWidget(body)
        return frame

    @staticmethod
    def _fmt_window(a):
        def f(t):
            return datetime.datetime.fromtimestamp(t).strftime("%a %H:%M")
        if a.onset and a.ends:
            return f(a.onset) + "  →  " + f(a.ends)
        if a.ends:
            return "until " + f(a.ends)
        if a.onset:
            return "from " + f(a.onset)
        return ""

    # ---- geometry / paint ---------------------------------------------

    def _panel_rect(self):
        w, h = self.width(), self.height()
        pw, ph = int(w * PANEL_FRACTION), int(h * PANEL_FRACTION)
        return QRect((w - pw) // 2, (h - ph) // 2, pw, ph)

    def resizeEvent(self, evt):
        self.scroll.setGeometry(self._panel_rect())
        super().resizeEvent(evt)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 180))
        panel = self._panel_rect()
        p.fillRect(panel, QColor(10, 16, 22, 230))
        p.setPen(QColor(190, 238, 255, 120))
        p.setBrush(Qt.NoBrush)
        p.drawRect(panel.adjusted(1, 1, -2, -2))
        p.end()

    def mousePressEvent(self, evt):
        # Click outside the scrollable panel dismisses; clicks inside scroll.
        if not self._panel_rect().contains(evt.pos()):
            self.dismissed.emit()
