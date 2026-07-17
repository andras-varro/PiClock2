from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QStackedWidget,
)

from ui.hourly_strip import HourlyStrip
from ui.daily_strip import DailyStrip


class _Tab(QLabel):
    """A clickable tab header label. Emits nothing; ForecastPanel wires clicks."""

    def __init__(self, text, on_click, parent=None):
        super().__init__(text, parent)
        self._on_click = on_click
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class _TabHeader(QFrame):
    """Holds the tab labels and paints a folder-tab silhouette around the active one.

    A dim baseline runs across the header; the active tab breaks through it as a
    raised trapezoid (slanted sides, open bottom) that merges into the content
    below — a classic file-folder tab.
    """

    _ACCENT = QColor("#50CBEB")
    _DIM = QColor(190, 238, 255, 60)
    _FILL = QColor(80, 203, 235, 26)

    def __init__(self, tabs, parent=None):
        super().__init__(parent)
        self.setObjectName("TabHeader")
        self.setStyleSheet("#TabHeader { background: transparent; }")
        self._tabs = tabs
        self._active = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(6)
        for t in tabs:
            layout.addWidget(t, 1)

    def set_active(self, index):
        self._active = index
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._tabs:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        yb = self.height() - 1.5          # baseline (tab bottom, open into content)
        yt = 2.0                          # tab top
        slant = 16.0                      # width of the angled "/ \" sides
        pad = 10.0                        # how far the tab overhangs its label

        g = self._tabs[self._active].geometry()
        x0 = max(2.0, g.left() - pad)
        x1 = min(w - 2.0, g.right() + pad)

        # Raised-tab fill (subtle), so the active tab reads as lifted.
        fill = QPainterPath()
        fill.moveTo(x0, yb)
        fill.lineTo(x0 + slant, yt)
        fill.lineTo(x1 - slant, yt)
        fill.lineTo(x1, yb)
        fill.closeSubpath()
        p.fillPath(fill, self._FILL)

        # Dim baseline on either side of the tab (content-area top edge).
        p.setPen(QPen(self._DIM, 2))
        p.drawLine(QPointF(0, yb), QPointF(x0, yb))
        p.drawLine(QPointF(x1, yb), QPointF(w, yb))

        # Bright tab silhouette: up the left slant, across the top, down the right.
        tab = QPainterPath()
        tab.moveTo(x0, yb)
        tab.lineTo(x0 + slant, yt)
        tab.lineTo(x1 - slant, yt)
        tab.lineTo(x1, yb)
        pen = QPen(self._ACCENT, 2.5)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawPath(tab)
        p.end()


class ForecastPanel(QFrame):
    """Right column: a Hourly | 10-Day tab header over a stacked view.

    Both child strips subscribe to app_state themselves, so switching tabs is a
    pure view swap — no refetch, and the hidden strip stays current.
    """

    _ACTIVE = ("font-size: 24px; font-weight: bold; color: #bef; "
               "background: transparent; padding: 2px 6px;")
    _INACTIVE = ("font-size: 24px; font-weight: bold; "
                 "color: rgba(190, 238, 255, 110); "
                 "background: transparent; padding: 2px 6px;")

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setObjectName("ForecastPanel")
        self.setStyleSheet("#ForecastPanel { background-color: transparent; }")

        self.tab_hourly = _Tab("Hourly", lambda: self._select(0))
        self.tab_daily = _Tab("10-Day", lambda: self._select(1))
        self.header = _TabHeader([self.tab_hourly, self.tab_daily], parent=self)
        self.header.setFixedHeight(48)

        self.stack = QStackedWidget(self)
        self.hourly = HourlyStrip(app_state, parent=self)
        self.daily = DailyStrip(app_state, parent=self)
        self.stack.addWidget(self.hourly)     # index 0
        self.stack.addWidget(self.daily)      # index 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.stack, 1)

        self._select(0)

    def _select(self, index):
        self.stack.setCurrentIndex(index)
        self.tab_hourly.setStyleSheet(self._ACTIVE if index == 0 else self._INACTIVE)
        self.tab_daily.setStyleSheet(self._ACTIVE if index == 1 else self._INACTIVE)
        self.header.set_active(index)
