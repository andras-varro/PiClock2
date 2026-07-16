from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ui.location_card import LocationCard
from ui.radar_widget import RadarWidget


class LocationColumn(QFrame):
    """
    Left column: stack of LocationCards on top, the small radar below.

    `radar_clicked` re-emits the RadarWidget's click so the main window can
    swap to the fullscreen radar page.
    """

    radar_clicked = pyqtSignal()

    def __init__(self, app_state, cfg, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.cfg = cfg

        self.setObjectName("LocationColumn")
        self.setStyleSheet(
            "#LocationColumn { background-color: transparent; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.cards = []
        for i, ld in enumerate(app_state.data):
            card = LocationCard(ld.location, parent=self)
            card.clicked.connect(lambda i=i: self._on_card_clicked(i))
            self.cards.append(card)
            layout.addWidget(card)

        # Small radar takes the remaining vertical space; click bubbles up to
        # the main window for the expanded lightbox view.
        self.radar = RadarWidget(app_state, cfg, parent=self)
        self.radar.clicked.connect(self.radar_clicked)
        layout.addWidget(self.radar, 1)

        app_state.location_changed.connect(self._on_active_changed)
        app_state.data_updated.connect(self._on_data_updated)
        app_state.alerts_updated.connect(self._on_alerts_updated)
        self._refresh_active()
        # Bind any data that already exists (e.g. a refresh that beat us here).
        for i, ld in enumerate(app_state.data):
            self.cards[i].set_conditions(ld.current)
            self.cards[i].set_alerts(ld.alerts)

    def _on_card_clicked(self, i):
        self.app_state.select(i)

    def _on_data_updated(self, i):
        if 0 <= i < len(self.cards):
            self.cards[i].set_conditions(self.app_state.data[i].current)

    def _on_alerts_updated(self, i):
        if 0 <= i < len(self.cards):
            self.cards[i].set_alerts(self.app_state.data[i].alerts)

    def _on_active_changed(self, _i):
        self._refresh_active()

    def _refresh_active(self):
        for i, card in enumerate(self.cards):
            card.set_active(i == self.app_state.active_index)
