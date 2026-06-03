"""Own Browser – Einstiegspunkt.

Chromium-Flags und das Custom-URL-Schema müssen gesetzt/registriert sein,
BEVOR QtWebEngine initialisiert bzw. die QApplication existiert.
"""

import os
import sys
from pathlib import Path

# Logging + Crash-Capture so früh wie möglich, damit auch Importfehler im Log landen.
from browser.applog import log, setup_logging

setup_logging()

_CHROMIUM_FLAGS = (
    # weniger Renderer-Prozesse -> weniger RAM bei vielen Tabs
    "--process-per-site --renderer-process-limit=4 "
    # verdeckte Fenster (z. B. hinter dem Settings-Fenster) nicht drosseln
    "--disable-features=CalculateNativeWinOcclusion "
    # GPU erzwingen, sonst rendert QtWebEngine backdrop-filter (Glas-Unschärfe) nicht,
    # wenn Chromium den Treiber per Blocklist auf Software-Rendering zurückstuft.
    "--ignore-gpu-blocklist --enable-gpu-rasterization"
)
# IMMER anhängen statt setdefault: wäre QTWEBENGINE_CHROMIUM_FLAGS schon (vom System)
# gesetzt, würde setdefault unsere Flags – inkl. der GPU-Flags – komplett ignorieren.
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip() + " " + _CHROMIUM_FLAGS
).strip()
log.info("Chromium-Flags: %s", os.environ["QTWEBENGINE_CHROMIUM_FLAGS"])

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

# Muss vor der QApplication-Instanz gesetzt sein (QtWebEngine + OpenGL).
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

# Custom-Schema fuer die Startseite – ebenfalls vor der QApplication.
from browser.newtab import register_app_scheme

register_app_scheme()

from browser.window import BrowserWindow
from browser.paths import ASSETS_DIR as _ASSETS


def _icon() -> QIcon | None:
    for name in ("icon.png", "icon.ico"):
        p = _ASSETS / name
        if p.exists():
            return QIcon(str(p))
    return None


def main() -> None:
    # Windows: eigene Taskbar-Identitaet, sonst zeigt die Taskbar das Python-Icon.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cipher.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Cipher")

    icon = _icon()
    if icon is not None:
        app.setWindowIcon(icon)

    window = BrowserWindow()
    log.info("Hauptfenster aufgebaut")
    if icon is not None:
        window.setWindowIcon(icon)

    if "--selftest" in sys.argv:
        # Aufbau testen, kurz Event-Loop laufen lassen, sauber beenden.
        QTimer.singleShot(1500, app.quit)
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
