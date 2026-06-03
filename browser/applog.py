"""Logging + Crash-Capture für Own Browser.

Schreibt nach ``logs/own-browser.log`` (rotierend). Fängt unbehandelte
Python-Exceptions ab – auch die aus Qt-Slots, die PyQt6 sonst mit ``abort()``
zum harten Absturz führen. Mit installiertem ``sys.excepthook`` wird der
Traceback stattdessen geloggt und die App läuft weiter. Qt-eigene Meldungen
(Warnungen/Fehler) landen im selben Log.
"""

import logging
import logging.handlers
import sys
import traceback
from pathlib import Path

from .paths import LOG_DIR  # schreibbar (Bundle: %LOCALAPPDATA%\Cipher, nicht Install-Dir)

LOG_FILE = LOG_DIR / "own-browser.log"

log = logging.getLogger("ownbrowser")


def setup_logging(level: int = logging.INFO) -> Path:
    """Logging einrichten (idempotent). Gibt den Pfad der Log-Datei zurück."""
    if log.handlers:  # schon eingerichtet
        return LOG_FILE
    LOG_DIR.mkdir(exist_ok=True)
    log.setLevel(level)
    log.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if sys.stderr is not None:  # bei pythonw (kein Konsolenfenster) ist stderr None
        sh = logging.StreamHandler()  # zusätzlich auf die Konsole
        sh.setFormatter(fmt)
        log.addHandler(sh)

    _install_excepthook()
    _install_qt_handler()
    log.info("=== Own Browser gestartet (Log: %s) ===", LOG_FILE)
    return LOG_FILE


def _install_excepthook() -> None:
    """Unbehandelte Exceptions loggen statt abzustürzen.

    PyQt6 ruft bei einer Exception in einem Slot ``sys.excepthook`` und beendet
    danach den Prozess – mit eigenem Hook (der nicht erneut wirft) loggen wir den
    Fehler und die App bleibt am Leben.
    """
    default_hook = sys.excepthook

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            default_hook(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.critical("Unbehandelte Exception:\n%s", text)

    sys.excepthook = hook


def _install_qt_handler() -> None:
    """Qt-Meldungen (qWarning/qCritical …) ins selbe Log umleiten."""
    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:  # noqa: BLE001 – ohne Qt einfach kein Qt-Handler
        return

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(mode, _context, message):
        log.log(levels.get(mode, logging.INFO), "Qt: %s", message)

    qInstallMessageHandler(handler)
