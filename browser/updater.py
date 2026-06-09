"""Auto-Update gegen GitHub Releases.

Mechanik: Beim Start (entprosselt, max. 1×/Tag — Throttle macht der Aufrufer) fragt
``Updater.check()`` die GitHub-API nach dem neuesten Release. Ist die Version neuer als
``version.__version__``, kommt ``update_available``. Der Aufrufer fragt den Nutzer; bei Ja
lädt ``download_and_launch`` das ``Cipher-Setup-*.exe`` und startet es — der Inno-Installer
macht ein In-Place-Upgrade (gleiche AppId), schliesst Cipher (Restart-Manager), ersetzt die
Dateien und startet neu. Eine laufende .exe kann sich nicht selbst überschreiben → genau
deshalb der Setup-Weg statt Datei-Patching.

Aktivierung: ``GITHUB_REPO`` auf ``"<user>/<repo>"`` setzen, sobald veröffentlicht. Leer =
Update-Check komplett aus (z. B. im Dev-Lauf).
"""

import json
import os
import subprocess
import tempfile

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .applog import log
from .version import __version__

# z. B. "damien/cipher" — leer lassen, solange es kein öffentliches Repo gibt.
GITHUB_REPO = "Darrenalder/Cipher"

_API_LATEST = "https://api.github.com/repos/{}/releases/latest"


def _ver_tuple(s: str) -> tuple:
    """'v0.2.10' -> (0, 2, 10). Nicht-Ziffern je Segment werden ignoriert."""
    out = []
    for part in str(s).strip().lstrip("vV").split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    try:
        return _ver_tuple(remote) > _ver_tuple(local)
    except (ValueError, TypeError):
        return False


class Updater(QObject):
    """Fragt GitHub Releases ab; meldet ein verfügbares Update per Signal."""

    update_available = pyqtSignal(dict)  # {version, url, page_url, notes}
    up_to_date = pyqtSignal(str)         # nichts Neueres da → aktuelle/neueste Version
    check_failed = pyqtSignal(str)       # Netz-/Antwortfehler (Fehlertext)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

    def check(self) -> None:
        if not GITHUB_REPO:
            return  # nicht konfiguriert → aus
        req = QNetworkRequest(QUrl(_API_LATEST.format(GITHUB_REPO)))
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setRawHeader(b"User-Agent", b"Cipher-Updater")
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_reply(reply))

    def _on_reply(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                log.info("Update-Check fehlgeschlagen: %s", reply.errorString())
                self.check_failed.emit(reply.errorString())
                return
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            tag = data.get("tag_name", "")
            if not is_newer(tag):
                self.up_to_date.emit((tag or __version__).lstrip("vV"))
                return
            url = ""
            for asset in data.get("assets", []):
                name = str(asset.get("name", "")).lower()
                if name.endswith(".exe") and "setup" in name:
                    url = asset.get("browser_download_url", "")
                    break
            log.info("Update verfügbar: %s (lokal %s)", tag, __version__)
            self.update_available.emit({
                "version": tag.lstrip("vV"),
                "url": url,
                "page_url": data.get("html_url", ""),
                "notes": data.get("body", "") or "",
            })
        except (ValueError, KeyError) as e:
            log.info("Update-Check: ungültige Antwort (%s)", e)
            self.check_failed.emit(str(e))
        finally:
            reply.deleteLater()


def download_and_launch(url: str, parent=None) -> None:
    """Setup.exe herunterladen (mit Fortschrittsdialog) und starten, dann Cipher beenden."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

    nam = QNetworkAccessManager(parent)
    reply = nam.get(QNetworkRequest(QUrl(url)))
    nam.setParent(parent)  # am Leben halten

    dlg = QProgressDialog("Lade Update …", "Abbrechen", 0, 100, parent)
    dlg.setWindowTitle("Cipher-Update")
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.setMinimumDuration(0)

    def on_progress(received: int, total: int) -> None:
        if total > 0:
            dlg.setMaximum(100)
            dlg.setValue(int(received * 100 / total))

    def on_finished() -> None:
        dlg.close()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            if reply.error() != QNetworkReply.NetworkError.OperationCanceledError:
                QMessageBox.warning(parent, "Update", "Download fehlgeschlagen:\n"
                                    + reply.errorString())
            reply.deleteLater()
            return
        data = bytes(reply.readAll())
        reply.deleteLater()
        try:
            fd, path = tempfile.mkstemp(suffix="-CipherSetup.exe")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except OSError as e:
            QMessageBox.warning(parent, "Update", "Konnte Update nicht speichern:\n" + str(e))
            return
        try:
            # Lautlos installieren: /VERYSILENT = kein Wizard, keine Lizenz, kein Klicken;
            # /SUPPRESSMSGBOXES = keine Rückfragen; /NORESTART = kein Windows-Neustart.
            # Das Setup schliesst Cipher (Restart-Manager), ersetzt die Dateien und startet
            # Cipher danach automatisch neu (installer.iss [Run] mit Check: WizardSilent).
            subprocess.Popen([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                             close_fds=True)
        except OSError as e:
            QMessageBox.warning(parent, "Update", "Konnte Setup nicht starten:\n" + str(e))
            return
        QApplication.instance().quit()  # Cipher schliessen, damit Dateien ersetzt werden

    reply.downloadProgress.connect(on_progress)
    dlg.canceled.connect(reply.abort)
    reply.finished.connect(on_finished)
    dlg.exec()
