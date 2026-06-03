r"""Zentrale Pfad-Auflösung — funktioniert sowohl im Dev-Lauf als auch im gebündelten
Installer (PyInstaller).

Zwei Kategorien:
- **Ressourcen** (read-only, mitgeliefert): ``themes/``-Vorlagen, ``assets/``. Im Bundle
  liegen sie in ``sys._MEIPASS`` (von PyInstaller gesetzt), im Dev im Projekt-Root.
- **Schreibbare Daten**: ``profile-data/`` (QtWebEngine-Profil), ``logs/`` und die
  veränderbaren Themes. Die dürfen NICHT ins Installationsverzeichnis (``Programme\`` ist
  read-only) → im Bundle nach ``%LOCALAPPDATA%\Cipher``, im Dev in den Projekt-Root.

Mitgelieferte Themes werden beim ersten Start einmal in den schreibbaren Themes-Ordner
kopiert (Seeding), damit Import/Löschen funktioniert.
"""

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Cipher"


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# --- Ressourcen (read-only) ------------------------------------------------
if _frozen():
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = RESOURCE_DIR / "assets"
_BUNDLED_THEMES = RESOURCE_DIR / "themes"

# --- Schreibbare Daten -----------------------------------------------------
if _frozen():
    _base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    DATA_DIR = Path(_base) / APP_NAME
else:
    DATA_DIR = Path(__file__).resolve().parent.parent

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

THEMES_DIR = DATA_DIR / "themes"
PROFILE_DIR = DATA_DIR / "profile-data"
LOG_DIR = DATA_DIR / "logs"


def _seed_themes() -> None:
    """Mitgelieferte Themes beim ersten Start in den schreibbaren Ordner kopieren.
    Im Dev sind Quelle und Ziel identisch (Projekt-Root) → no-op."""
    try:
        if THEMES_DIR != _BUNDLED_THEMES and _BUNDLED_THEMES.is_dir() and not THEMES_DIR.exists():
            shutil.copytree(_BUNDLED_THEMES, THEMES_DIR)
    except OSError:
        pass  # Themes fehlen dann → load_themes fällt auf DEFAULT_THEME zurück


_seed_themes()
