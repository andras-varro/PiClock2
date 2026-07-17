from typing import List

from PyQt5.QtCore import QObject, pyqtSignal

from models import Location, LocationData


class AppState(QObject):
    """
    Central app state: which location is active, and per-location weather data.

    Widgets subscribe to `location_changed` (active index changed) and
    `data_updated` (new weather data for some location) to refresh themselves.
    """

    location_changed = pyqtSignal(int)
    location_selected = pyqtSignal(int)   # fires on every selection, incl. re-tap
    data_updated = pyqtSignal(int)
    alerts_updated = pyqtSignal(int)

    def __init__(self, locations: List[Location]):
        super().__init__()
        self._active = 0
        self.data: List[LocationData] = [LocationData(location=l) for l in locations]

    @property
    def active_index(self) -> int:
        return self._active

    @property
    def active(self) -> LocationData:
        return self.data[self._active]

    def set_active(self, i: int):
        if 0 <= i < len(self.data) and i != self._active:
            self._active = i
            self.location_changed.emit(i)

    def select(self, i: int):
        """User picked a location (possibly the active one again).

        Emits location_changed only on an actual change (so e.g. the radar
        doesn't needlessly refetch), but always emits location_selected — the
        alert banner uses that to re-appear on a re-tap.
        """
        if not (0 <= i < len(self.data)):
            return
        if i != self._active:
            self._active = i
            self.location_changed.emit(i)
        self.location_selected.emit(i)

    def update_weather(self, i: int, current, hourly, daily, when):
        d = self.data[i]
        d.current = current
        d.hourly = hourly
        d.daily = daily
        d.last_updated = when
        self.data_updated.emit(i)

    def update_alerts(self, i: int, alerts):
        self.data[i].alerts = alerts or []
        self.alerts_updated.emit(i)
