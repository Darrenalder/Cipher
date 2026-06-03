"""Ein einzelner Tab.

Kapselt die QWebEngineView samt Lifecycle-Steuerung. Genau hier sitzt der
Effizienz-Kern: Active / Frozen / Discarded entsprechen Chromiums
Page-Lifecycle und bestimmen, wie viel RAM/CPU ein Hintergrund-Tab belegt.
"""

from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

from .webpage import WebPage
from .profile import get_profile

State = QWebEnginePage.LifecycleState


class BrowserTab(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = WebPage(get_profile(), self)
        self.setPage(self._page)
        self.pinned = False

    # --- Hilfen -----------------------------------------------------------
    def set_create_tab_callback(self, callback) -> None:
        self._page.set_create_tab_callback(callback)

    def is_audible(self) -> bool:
        try:
            return self._page.recentlyAudible()
        except Exception:
            return False

    def lifecycle_state(self):
        try:
            return self._page.lifecycleState()
        except Exception:
            return State.Active

    # --- Lifecycle --------------------------------------------------------
    def set_foreground(self) -> None:
        """Tab ist sichtbar/aktiv – weckt ggf. aus Frozen/Discarded auf."""
        try:
            self._page.setVisible(True)
            self._page.setLifecycleState(State.Active)
        except Exception:
            pass

    def set_background(self) -> None:
        """Tab ist nicht mehr im Vordergrund (Vorbedingung fuers Einfrieren)."""
        try:
            self._page.setVisible(False)
        except Exception:
            pass

    def freeze(self) -> None:
        """JS anhalten, CPU ~0, RAM sinkt. Inhalt bleibt im Speicher."""
        try:
            self._page.setVisible(False)
            if self._page.lifecycleState() == State.Active:
                self._page.setLifecycleState(State.Frozen)
        except Exception:
            pass

    def discard(self) -> None:
        """Renderer-Prozess freigeben (RAM weg). Laedt beim Aufwecken neu.
        Discarded ist nur aus Frozen erreichbar – darum ggf. erst einfrieren.
        """
        try:
            self._page.setVisible(False)
            if self._page.lifecycleState() == State.Active:
                self._page.setLifecycleState(State.Frozen)
            self._page.setLifecycleState(State.Discarded)
        except Exception:
            pass
