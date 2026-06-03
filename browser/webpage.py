"""Eigene QWebEnginePage – faengt window.open / target=_blank ab und
oeffnet stattdessen einen neuen Tab im selben Fenster.
"""

from PyQt6.QtWebEngineCore import QWebEnginePage


class WebPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._create_tab_callback = None

    def set_create_tab_callback(self, callback) -> None:
        """callback() muss eine neue View (BrowserTab) liefern oder None."""
        self._create_tab_callback = callback

    def createWindow(self, _type):  # noqa: N802 (Qt-Signatur)
        if self._create_tab_callback is not None:
            view = self._create_tab_callback()
            if view is not None:
                return view.page()
        return None
