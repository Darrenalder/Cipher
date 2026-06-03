"""Tab-Sleeping-Manager.

Scannt periodisch alle Tabs und friert Hintergrund-Tabs nach Ablauf der
Timer ein (Frozen) bzw. verwirft sie (Discarded). Angepinnte und gerade
Audio spielende Tabs sind ausgenommen.
"""

import time

from PyQt6.QtCore import QObject, QTimer

from .tab import State


class TabSleeper(QObject):
    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.tabs = tab_widget          # QTabWidget
        self.enabled = True
        self.freeze_after = 30          # Sekunden im Hintergrund -> Frozen
        self.discard_after = 600        # Sekunden im Hintergrund -> Discarded
        self._bg_since = {}             # id(tab) -> monotone Zeit (Hintergrund seit)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan)
        self._timer.start(5000)         # alle 5 s pruefen

    # --- Scan-Schleife ----------------------------------------------------
    def _scan(self) -> None:
        if not self.enabled:
            return
        current = self.tabs.currentWidget()
        now = time.monotonic()

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None:
                continue

            # Vordergrund / ausgenommene Tabs nie schlafen legen.
            if tab is current or tab.pinned or tab.is_audible():
                self._bg_since.pop(id(tab), None)
                continue

            since = self._bg_since.get(id(tab))
            if since is None:
                # gerade in den Hintergrund gerutscht -> Zeitstempel + unsichtbar
                self._bg_since[id(tab)] = now
                tab.set_background()
                continue

            elapsed = now - since
            if elapsed >= self.discard_after:
                tab.discard()
            elif elapsed >= self.freeze_after:
                tab.freeze()

    # --- Game-Mode --------------------------------------------------------
    def freeze_all_background(self) -> None:
        """Sofort alle Hintergrund-Tabs einfrieren (RAM/CPU ans Spiel)."""
        current = self.tabs.currentWidget()
        now = time.monotonic()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or tab is current or tab.pinned or tab.is_audible():
                continue
            tab.freeze()
            self._bg_since[id(tab)] = now

    def discard_all_background(self) -> None:
        """Härter als freeze_all: Hintergrund-Tabs verwerfen (Renderer-Prozess
        weg → RAM frei). Für die RAM-Limit-Drosselung."""
        current = self.tabs.currentWidget()
        now = time.monotonic()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is None or tab is current or tab.pinned or tab.is_audible():
                continue
            tab.discard()
            self._bg_since[id(tab)] = now

    # --- Status -----------------------------------------------------------
    def sleeping_count(self) -> int:
        n = 0
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is not None and tab.lifecycle_state() != State.Active:
                n += 1
        return n
