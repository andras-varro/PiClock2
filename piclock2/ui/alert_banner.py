"""
Top alert banner.

A strip over the clock area, shown when the active location has weather alerts.
Background is colored by the most-severe alert. No emoji glyphs — the Pi's
DejaVu font renders them as tofu boxes — so the warning mark and the close
button are drawn.

Interaction:
  - click the banner body  -> open the detail overlay (clicked signal)
  - click the ✕ at the right -> dismiss (hide) it for now
A dismissed banner re-appears when the user re-selects the location, or when
the alert set changes (new information).
"""

from PyQt5.QtCore import Qt, QRect, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

from models import severity_color, severity_text_color

BANNER_HEIGHT = 74


class AlertBanner(QWidget):
    clicked = pyqtSignal()
    shown_changed = pyqtSignal()        # emitted when visibility flips (re-layout)

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setFixedHeight(BANNER_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        self._text = ""
        self._bg = QColor("#8e8e93")
        self._fg = QColor("#ffffff")
        self._dismissed = False         # user closed the current alert set
        self._last_sig = None           # signature of the alerts last presented

        app_state.alerts_updated.connect(self._on_alerts_updated)
        app_state.location_selected.connect(self._on_location_selected)
        self.hide()

    # ---- triggers ------------------------------------------------------

    def _on_alerts_updated(self, i):
        if i == self.app_state.active_index:
            self._present(force=False)   # new info may override a dismissal

    def _on_location_selected(self, i):
        if i == self.app_state.active_index:
            self._present(force=True)    # re-selecting always re-shows

    @staticmethod
    def _sig(alerts):
        return tuple((a.event, a.severity, a.onset, a.ends) for a in alerts)

    def _present(self, force):
        alerts = self.app_state.active.alerts
        if not alerts:
            self._last_sig = None
            self._dismissed = False
            if self.isVisible():
                self.hide()
                self.shown_changed.emit()
            return

        sig = self._sig(alerts)
        # Show when forced (re-select), when not currently dismissed, or when
        # the alert set changed since we were dismissed (new information).
        if not (force or not self._dismissed or sig != self._last_sig):
            return

        self._dismissed = False
        self._last_sig = sig
        top = alerts[0]
        extra = "   (+%d more)" % (len(alerts) - 1) if len(alerts) > 1 else ""
        self._text = top.event + extra
        self._bg = QColor(severity_color(top.severity))
        self._fg = QColor(severity_text_color(top.severity))
        self.show()
        self.shown_changed.emit()       # MainWindow re-pins + raises
        self.update()

    # ---- geometry ------------------------------------------------------

    def _close_rect(self):
        h = self.height()
        sz = int(h * 0.46)
        margin = 18
        return QRect(self.width() - sz - margin, (h - sz) // 2, sz, sz)

    # ---- paint / input -------------------------------------------------

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        p.fillRect(rect, self._bg)

        # Warning triangle on the left, in the text color, with a punched "!".
        h = rect.height()
        cx, cy, s = 40, h / 2.0, h * 0.30
        tri = QPolygonF([
            QPointF(cx, cy - s),
            QPointF(cx - s * 1.15, cy + s),
            QPointF(cx + s * 1.15, cy + s),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(self._fg)
        p.drawPolygon(tri)
        p.setPen(self._bg)
        p.setFont(QFont("Arial", int(h * 0.30), QFont.Black))
        p.drawText(int(cx - s), int(cy - s * 0.55), int(s * 2), int(s * 1.7),
                   Qt.AlignCenter, "!")

        # Alert text (leave room for the close button on the right).
        cr = self._close_rect()
        p.setPen(self._fg)
        p.setFont(QFont("Arial", 28, QFont.Bold))
        p.drawText(rect.adjusted(80, 0, -(rect.width() - cr.left()) - 12, 0),
                   Qt.AlignVCenter | Qt.AlignLeft, self._text)

        # Close (✕) button on the right.
        pen = QPen(self._fg)
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        pad = int(cr.width() * 0.28)
        p.drawLine(cr.left() + pad, cr.top() + pad,
                   cr.right() - pad, cr.bottom() - pad)
        p.drawLine(cr.left() + pad, cr.bottom() - pad,
                   cr.right() - pad, cr.top() + pad)
        p.end()

    def mousePressEvent(self, evt):
        if self._close_rect().adjusted(-6, -6, 6, 6).contains(evt.pos()):
            self._dismissed = True
            self.hide()
            self.shown_changed.emit()
        else:
            self.clicked.emit()
