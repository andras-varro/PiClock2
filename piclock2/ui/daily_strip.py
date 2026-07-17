import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout

from models import aqi_dot_html, aqi_value, aqi_scale_for

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


class DailyRow(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DailyRow")
        self.setStyleSheet(
            "#DailyRow { "
            "background-color: rgba(0, 0, 0, 60); "
            "border: 1px solid rgba(190, 238, 255, 40); "
            "border-radius: 5px; "
            "} "
            "QLabel { color: #bef; background: transparent; }"
        )

        self.day_label = QLabel("—")
        self.day_label.setObjectName("DyDay")
        self.day_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.day_label.setFixedWidth(90)

        self.icon_label = QLabel("·")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedWidth(56)

        self.rain_label = QLabel("")
        self.rain_label.setObjectName("DyRain")
        self.rain_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #7ec8ff;")
        self.rain_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rain_label.setFixedWidth(60)

        self.aqi_label = QLabel("")
        self.aqi_label.setObjectName("DyAqi")
        self.aqi_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.aqi_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.aqi_label.setFixedWidth(64)

        # High / low, e.g. "82° / 64°".
        self.temp_label = QLabel("--° / --°")
        self.temp_label.setObjectName("DyTemp")
        self.temp_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.temp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.temp_label.setFixedWidth(132)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        layout.addWidget(self.day_label)
        layout.addWidget(self.icon_label)
        layout.addStretch(1)
        layout.addWidget(self.rain_label)
        layout.addWidget(self.aqi_label)
        layout.addWidget(self.temp_label)

    def set_forecast(self, day_str, desc, temp_max, temp_min, units, icon=None,
                     rain_pct=0.0, aqi=None, aqi_scale="us"):
        # `desc` (the condition text) is intentionally not shown — the icon
        # carries the condition, and single long words like "Thunderstorm"
        # cannot wrap and would clip the narrow column.
        self.day_label.setText(day_str)
        # Hi/lo omit the F/C letter to save width; the active card carries units.
        self.temp_label.setText(
            "{:.0f}° / {:.0f}°".format(temp_max, temp_min))
        self.rain_label.setText(
            "{:.0f}%".format(rain_pct) if rain_pct and rain_pct > 0 else "")
        self.aqi_label.setText(aqi_dot_html(aqi, aqi_scale))
        pix = _load_icon(icon, 48)
        if pix is not None:
            self.icon_label.setPixmap(pix)
        else:
            self.icon_label.clear()
            self.icon_label.setText("·")

    def clear_forecast(self):
        self.day_label.setText("—")
        self.temp_label.setText("--° / --°")
        self.rain_label.setText("")
        self.aqi_label.setText("")
        self.icon_label.clear()
        self.icon_label.setText("·")


class DailyStrip(QFrame):
    """10-day daily forecast rows for the active location."""

    N_ROWS = 10

    def __init__(self, app_state, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.setObjectName("DailyStrip")
        self.setStyleSheet("#DailyStrip { background-color: transparent; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        self.rows = []
        for i in range(self.N_ROWS):
            row = DailyRow(parent=self)
            self.rows.append(row)
            layout.addWidget(row, 1)     # equal stretch -> fill column height

        app_state.data_updated.connect(self._on_data_updated)
        app_state.location_changed.connect(lambda _i: self._refresh())

    def _on_data_updated(self, i):
        if i == self.app_state.active_index:
            self._refresh()

    def _refresh(self):
        ld = self.app_state.active
        scale = aqi_scale_for(ld.location)
        for i, row in enumerate(self.rows):
            if i < len(ld.daily):
                d = ld.daily[i]
                row.set_forecast(d.weekday_label, d.description, d.temp_max,
                                 d.temp_min, d.units, d.icon,
                                 rain_pct=d.precip_prob_max,
                                 aqi=aqi_value(d, scale), aqi_scale=scale)
            else:
                row.clear_forecast()
