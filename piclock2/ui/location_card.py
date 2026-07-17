import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout

from models import (
    wind_compass, severity_color, severity_text_color,
    aqi_dot_html, aqi_value, aqi_scale_for,
)

ICONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "icons-lightblue",
)


def _load_icon(name, size):
    if not name:
        return None
    path = os.path.join(ICONS_DIR, name + ".png")
    if not os.path.isfile(path):
        return None
    pix = QPixmap(path)
    if pix.isNull():
        return None
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class LocationCard(QFrame):
    """
    One clickable card in the left column.

    Two visual modes, driven by set_active():
      - compact (inactive): a single line — icon + name + temp.
      - full (active): a taller card — icon + name + temp on top, then two
        detail rows (Feels / Humidity, then Wind [+ pressure if it fits]).

    No textual description is shown; the weather icon conveys the condition.
    The last CurrentConditions is cached so the detail rows can be (re)built
    whenever the card becomes active.
    """

    clicked = pyqtSignal()

    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.location = location
        self._active = False
        self._current = None
        self._alerts = []

        self.setObjectName("LocationCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.NoFrame)

        self.name_label = QLabel(location.name)
        self.name_label.setObjectName("LocName")
        self.name_label.setWordWrap(True)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("LocIcon")
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.temp_label = QLabel("--°")
        self.temp_label.setObjectName("LocTemp")
        self.temp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        top.addWidget(self.icon_label, 0)
        top.addWidget(self.name_label, 1)
        top.addWidget(self.temp_label, 0)

        # Alert pill (shown only when this location has active alerts).
        self.alert_label = QLabel("")
        self.alert_label.setObjectName("LocAlert")
        self.alert_label.setVisible(False)

        # Detail rows (shown only when active).
        self.detail1 = QLabel("")     # Feels / Humidity
        self.detail1.setObjectName("LocDetail")
        self.detail2 = QLabel("")     # Wind (+ pressure)
        self.detail2.setObjectName("LocDetail")
        self.detail3 = QLabel("")     # AQI (colored dot + number)
        self.detail3.setObjectName("LocDetail")
        self.detail1.setVisible(False)
        self.detail2.setVisible(False)
        self.detail3.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(3)
        outer.addLayout(top)
        outer.addWidget(self.alert_label)
        outer.addWidget(self.detail1)
        outer.addWidget(self.detail2)
        outer.addWidget(self.detail3)

        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        if active == self._active:
            return
        self._active = active
        self._sync_detail()
        self._apply_style()

    def set_alerts(self, alerts):
        """Bind active weather alerts (list, possibly empty) to this card."""
        self._alerts = alerts or []
        if self._alerts:
            top = self._alerts[0]
            n = len(self._alerts)
            suffix = "  +%d" % (n - 1) if n > 1 else ""
            # ASCII "!" marker — the Pi's font has no warning emoji glyph.
            self.alert_label.setText("! " + top.event + suffix)
            self.alert_label.setStyleSheet(
                "#LocAlert { background-color: " + severity_color(top.severity) + "; "
                "color: " + severity_text_color(top.severity) + "; "
                "border-radius: 6px; padding: 2px 8px; "
                "font-size: 17px; font-weight: bold; }")
            self.alert_label.setVisible(True)
        else:
            self.alert_label.setVisible(False)
        self._apply_style()

    def set_conditions(self, current):
        """Bind a CurrentConditions dataclass (or None) to this card."""
        self._current = current
        if current is None:
            self.temp_label.setText("--°")
            self.icon_label.clear()
            self._sync_detail()
            return
        unit = "°F" if current.units == "imperial" else "°C"
        self.temp_label.setText("{:.0f}{}".format(current.temperature, unit))
        pix = _load_icon(current.icon, 64 if self._active else 46)
        if pix is not None:
            self.icon_label.setPixmap(pix)
        else:
            self.icon_label.clear()
        self._sync_detail()

    def _sync_detail(self):
        """Show + fill the detail rows when active and data is available."""
        show = self._active and self._current is not None
        self.detail1.setVisible(show)
        self.detail2.setVisible(show)
        if not show:
            self.detail3.setVisible(False)
            return
        c = self._current
        spd_unit = "mph" if c.units == "imperial" else "km/h"
        self.detail1.setText(
            "Feels <b>{:.0f}°</b>&nbsp;&nbsp;&nbsp;Humidity <b>{:.0f}%</b>".format(
                c.feels_like, c.humidity))
        # Pressure dropped: at the larger active font it pushed the wind line
        # past the card edge, and it's the least-important field.
        self.detail2.setText("Wind <b>{:.0f} {} {}</b>".format(
            c.wind_speed, spd_unit, wind_compass(c.wind_direction)).rstrip())
        # AQI on its own line so it never crowds the wind line at the active font.
        scale = aqi_scale_for(self.location)
        dot = aqi_dot_html(aqi_value(c, scale), scale)
        if dot:
            self.detail3.setText("AQI " + dot)
            self.detail3.setVisible(True)
        else:
            self.detail3.setVisible(False)

    def _apply_style(self):
        if self._active:
            border = "#50CBEB"
            bg = "rgba(80, 203, 235, 30)"
            dot = "● "
            name_pt, temp_pt, detail_pt = 30, 54, 26
            self.icon_label.setFixedSize(64, 64)
        else:
            border = "rgba(190, 238, 255, 60)"
            bg = "rgba(0, 0, 0, 60)"
            dot = "   "
            name_pt, temp_pt, detail_pt = 20, 32, 20
            self.icon_label.setFixedSize(46, 46)
        # An active alert tints the border to its severity color, so an alerted
        # location stands out in the column even while inactive.
        if self._alerts:
            border = severity_color(self._alerts[0].severity)
        self.name_label.setText(dot + self.location.name)
        self.setStyleSheet(
            "#LocationCard { "
            "background-color: " + bg + "; "
            "border: 2px solid " + border + "; "
            "border-radius: 8px; "
            "} "
            "QLabel { color: #bef; background: transparent; } "
            "#LocName { font-size: " + str(name_pt) + "px; font-weight: bold; } "
            "#LocTemp { font-size: " + str(temp_pt) + "px; font-weight: bold; } "
            "#LocDetail { font-size: " + str(detail_pt) + "px; "
            "color: rgba(190, 238, 255, 210); }"
        )
