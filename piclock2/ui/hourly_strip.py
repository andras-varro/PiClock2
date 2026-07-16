import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout

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


class HourlyRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HourlyRow")
        self._base_style = (
            "#HourlyRow { "
            "background-color: rgba(0, 0, 0, %d); "
            "border: 1px solid rgba(190, 238, 255, %d); "
            "border-radius: 5px; "
            "} "
            "QLabel { color: #bef; background: transparent; }"
        )
        self._set_highlight(False)

        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("HrTime")
        self.time_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.time_label.setFixedWidth(92)

        self.icon_label = QLabel("·")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedWidth(58)

        self.desc_label = QLabel("—")
        self.desc_label.setStyleSheet("font-size: 22px;")
        self.desc_label.setWordWrap(True)

        self.rain_label = QLabel("")
        self.rain_label.setObjectName("HrRain")
        self.rain_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #7ec8ff;")
        self.rain_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rain_label.setFixedWidth(74)

        self.temp_label = QLabel("--°")
        self.temp_label.setStyleSheet("font-size: 32px; font-weight: bold;")
        self.temp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.temp_label.setFixedWidth(82)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        layout.addWidget(self.time_label)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.desc_label, 1)
        layout.addWidget(self.rain_label)
        layout.addWidget(self.temp_label)

    def _set_highlight(self, on):
        # Current hour gets a slightly brighter background/border.
        self.setStyleSheet(self._base_style % ((90, 110) if on else (60, 40)))

    def set_forecast(self, time_str, desc, temp, units, icon=None,
                     rain_pct=0.0, highlight=False):
        self.time_label.setText(time_str)
        self.desc_label.setText(desc)
        unit = "°F" if units == "imperial" else "°C"
        self.temp_label.setText("{:.0f}{}".format(temp, unit))
        # Chance of rain only when meaningful, to keep the row uncluttered.
        # No droplet glyph — the Pi's font has no emoji and renders it as a
        # tofu box; the blue percentage reads clearly as precip chance.
        self.rain_label.setText(
            "{:.0f}%".format(rain_pct) if rain_pct and rain_pct > 0 else "")
        self._set_highlight(highlight)
        pix = _load_icon(icon, 50)
        if pix is not None:
            self.icon_label.setPixmap(pix)
        else:
            self.icon_label.clear()
            self.icon_label.setText("·")


class HourlyStrip(QFrame):
    """Right column: hourly forecast rows, distributed to fill the height."""

    N_ROWS = 12

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setObjectName("HourlyStrip")
        self.setStyleSheet("#HourlyStrip { background-color: transparent; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        self.rows = []
        for i in range(self.N_ROWS):
            row = HourlyRow(parent=self)
            self.rows.append(row)
            layout.addWidget(row, 1)     # equal stretch -> fill column height

        app_state.data_updated.connect(self._on_data_updated)
        app_state.location_changed.connect(lambda _i: self._refresh())

    def _on_data_updated(self, i):
        if i == self.app_state.active_index:
            self._refresh()

    def _refresh(self):
        ld = self.app_state.active
        units = ld.location.units
        for i, row in enumerate(self.rows):
            if i < len(ld.hourly):
                f = ld.hourly[i]
                label = f.clock_time or ("now" if i == 0 else "+{}h".format(i))
                row.set_forecast(label, f.description, f.temperature, f.units,
                                 f.icon, rain_pct=f.precipitation_probability,
                                 highlight=(i == 0))
            else:
                row.set_forecast("--:--", "—", 0, units)
