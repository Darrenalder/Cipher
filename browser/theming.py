"""Theme-System.

Ein Theme ist eine JSON-Datei in ``themes/`` mit Farbwerten. Die Datei wird
in eine QSS-Vorlage (Qt Style Sheet) eingesetzt und auf die ganze App
angewandt. Fehlende Schluessel fallen auf DEFAULT_THEME zurueck.

Der Ecken-Radius ist KEIN Theme-Wert, sondern eine globale Nutzer-Einstellung
(Slider in Aussehen) und wird in build_qss() separat reingereicht.

Optional darf ein Theme ``extra_qss`` enthalten: roher QSS-Text, hinten angehaengt.

Format (themes/<name>.json):
    {
      "name": "Mein Theme",
      "accent": "#00e5d0",
      "bg": "#0f1216",
      "bg_alt": "#161b22",
      "bg_elevated": "#1f2630",
      "text": "#e6e9ef",
      "text_dim": "#8b93a7",
      "border": "#2a3142",
      "danger": "#ff4d6d"
    }
"""

import base64
import json
from pathlib import Path
from string import Template

from .paths import THEMES_DIR  # schreibbar (Dev: Projekt, Bundle: %LOCALAPPDATA%\Cipher)

DEFAULT_THEME = {
    "name": "Default",
    "accent": "#00e5d0",
    "bg": "#0f1216",
    "bg_alt": "#161b22",
    "bg_elevated": "#1f2630",
    "text": "#e6e9ef",
    "text_dim": "#8b93a7",
    "border": "#2a3142",
    "danger": "#ff4d6d",
}

# Mitgelieferte Presets → Gruppe „Standard"; alles andere → „Erweiterung".
BUILTIN_THEME_NAMES = {
    "Neon Cyan", "GX Red", "Violet", "Slate", "Matrix Green",
    "Midnight Blue", "Aurora", "Starfield", "Default",
}

# Platzhalter im string.Template-Stil ($name / ${name}). QSS nutzt keine
# $-Zeichen, darum keine Kollision mit den geschweiften Klammern.
_QSS = Template(
    """
QMainWindow, QWidget {
    background-color: $bg;
    color: $text;
    font-size: 13px;
}
/* Immersiv: Host + Container transparent → Fenster-Wallpaper scheint durch. */
#FramelessHost, #Topbar, #Body { background: transparent; }
QToolBar {
    background-color: $bar_bg;
    border: none;
    padding: 6px 10px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: transparent;
    border: none;
    border-radius: ${radius_sm}px;
    padding: 7px 9px;
    color: $text;
}
QToolBar QToolButton:hover { background-color: $bg_elevated; }
QToolBar QToolButton:disabled { color: $text_dim; }
QToolBar QToolButton:checked { background-color: $accent; color: $on_accent; }
QToolButton::menu-indicator { image: none; }
QLineEdit {
    background-color: $input_bg;
    border: 1px solid $border;
    border-radius: ${radius}px;
    padding: 8px 16px;
    color: $text;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:focus { border: 1px solid $accent; }
QTabWidget::pane { border: none; }
QTabBar { background: transparent; qproperty-drawBase: 0; }
QTabBar::tab {
    background: $bar_bg;
    color: $text_dim;
    padding: 8px 6px 8px 14px;
    margin-right: 3px;
    border-top-left-radius: ${radius_sm}px;
    border-top-right-radius: ${radius_sm}px;
    border-bottom-left-radius: ${radius_xs}px;
    border-bottom-right-radius: ${radius_xs}px;
    min-width: 90px;
    max-width: 240px;
}
QTabBar::tab:hover { background: $input_bg; color: $text; }
QTabBar::tab:selected { background: $input_bg; color: $text; border-bottom: 2px solid $accent; }
QToolButton[tabclose="1"] { background: transparent; border: none; border-radius: ${radius_xs}px; }
QToolButton[tabclose="1"]:hover { background: $border; }
QToolButton[tabplus="1"] {
    background: transparent; border: none; border-radius: ${radius_sm}px;
    color: $text; font-size: 17px;
}
QToolButton[tabplus="1"]:hover { background: $bg_elevated; }
QStatusBar { background-color: $bar_bg; color: $text_dim; }
QStatusBar::item { border: none; }
QStatusBar > QWidget { background: transparent; }
QStatusBar QLabel { color: $text_dim; background: transparent; padding: 0 6px; }
QMenu {
    background-color: $bg_elevated; color: $text;
    border: 1px solid $border; padding: 4px; border-radius: ${radius_sm}px;
}
QMenu::item { padding: 6px 22px 6px 18px; border-radius: ${radius_xs}px; }
QMenu::item:selected { background-color: $accent; color: $on_accent; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QScrollBar:vertical { background: $bg; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $bg_elevated; border-radius: 6px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background-color: $bg_elevated; color: $text; border: 1px solid $border; }

/* Panel + Icon-Rail */
#SettingsPanel { background-color: $bg_alt; border-left: 1px solid $border; }
#PanelRail { background-color: $bar_bg; border-left: 1px solid $border; }
QToolButton[rail="1"] { background: transparent; border: none; border-radius: ${radius_sm}px; }
QToolButton[rail="1"]:hover { background: $bg_elevated; }
QToolButton[rail="1"]:checked { background: $bg_elevated; }
#SettingsCats {
    background: $bg_alt; border: none; outline: none; padding: 6px;
}
#SettingsCats::item {
    padding: 9px 12px; border-radius: ${radius_sm}px; color: $text;
}
#SettingsCats::item:hover { background: $bg_elevated; }
#SettingsCats::item:selected { background: $accent; color: $on_accent; }
QToolButton#ThemeCard {
    background: $bg_alt; border: 1px solid $border; border-radius: ${radius_sm}px;
    padding: 6px; color: $text_dim;
}
QToolButton#ThemeCard:hover { border-color: $accent; }
QToolButton#ThemeCard[active="true"] { border: 2px solid $accent; color: $text; }
QToolButton#GroupHeader {
    background: transparent; border: none; color: $text;
    font-weight: 600; font-size: 14px; padding: 6px 2px;
}
QToolButton#GroupHeader:hover { color: $accent; }
QScrollArea { background: transparent; border: none; }
QLabel[role="title"] { font-size: 16px; font-weight: 600; color: $text; }
QLabel[role="section"] { color: $text_dim; font-weight: 600; padding-top: 8px; }
QComboBox {
    background: $bg_elevated; border: 1px solid $border; border-radius: ${radius_sm}px;
    padding: 6px 10px; color: $text;
}
QComboBox:hover { border-color: $accent; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: $bg_elevated; color: $text; border: 1px solid $border;
    selection-background-color: $accent; selection-color: $on_accent; outline: none;
}
QSlider { background: transparent; }
QSlider::groove:horizontal { height: 4px; background: $bg_elevated; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::add-page:horizontal { background: $bg_elevated; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: $text;
}
QSlider::handle:horizontal:hover { background: $accent; }
QCheckBox { color: $text; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: ${radius_xs}px;
    border: 1px solid $border; background: $bg_elevated;
}
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check_uri"); }
QPushButton {
    background: $bg_elevated; border: 1px solid $border; border-radius: ${radius_sm}px;
    padding: 6px 12px; color: $text;
}
QPushButton:hover { border-color: $accent; }

/* Fenster-Steuerung (rahmenloses Fenster) */
QToolButton[wctl="1"] { background: transparent; border: none; border-radius: 0; }
QToolButton[wctl="1"]:hover { background: $bg_elevated; }
QToolButton[wclose="1"]:hover { background: $danger; }
"""
)


def load_themes() -> dict:
    """Liest alle themes/*.json und liefert {name: theme-dict}."""
    themes: dict = {}
    if THEMES_DIR.is_dir():
        for path in sorted(THEMES_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            name = str(data.get("name", path.stem))
            themes[name] = {**DEFAULT_THEME, **data, "name": name, "__path__": str(path)}
    if not themes:
        themes[DEFAULT_THEME["name"]] = dict(DEFAULT_THEME)
    return themes


def _rgb(hexstr):
    s = str(hexstr).lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _lum(hexstr):
    r, g, b = _rgb(hexstr)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _lighten(hexstr, t):
    r, g, b = _rgb(hexstr)
    return "#%02x%02x%02x" % (
        round(r + (255 - r) * t),
        round(g + (255 - g) * t),
        round(b + (255 - b) * t),
    )


def _glossy_qss(m: dict) -> str:
    """Glanz-Hinweis auf den (jetzt translucenten) Leisten: nur eine helle Oberkante.
    KEINE opaken Hintergrund-Verläufe mehr — die würden die Immersiv-Transluzenz
    überdecken (das Fenster-Wallpaper soll hinter den Leisten durchscheinen)."""
    hl = _lighten(m["bg_alt"], 0.22)
    return f"""
QToolBar {{ border-top: 1px solid {hl}; }}
QStatusBar {{ border-top: 1px solid {hl}; }}
QLineEdit {{ border-top: 1px solid {hl}; }}
"""


def build_qss(theme: dict, radius: int = 12, glossy: bool = True,
              glass_chrome: bool = True, chrome_alpha: int = 55) -> str:
    """Setzt Theme-Farben + globalen Ecken-Radius in die QSS-Vorlage ein.

    radius steuert die Adressleiste (gross); Buttons/Tabs (radius_sm) und
    Menues/Checkboxen (radius_xs) werden proportional abgeleitet.
    glossy=True hängt ein Glanz-Overlay an (Verlauf + helle Oberkante).
    """
    radius = max(0, int(radius))
    merged = {
        **DEFAULT_THEME,
        **theme,
        "radius": radius,
        "radius_sm": round(radius * 0.6),
        "radius_xs": round(radius * 0.45),
    }
    # Akzent für Highlights aufhellen, wenn er zu dunkel ist (sonst dunkel-auf-
    # dunkel, unlesbar). on_accent = Textfarbe auf dem Akzent, hell oder dunkel
    # je nach Helligkeit. Gilt nur fürs Chrome-QSS; Startseite nutzt Roh-Akzent.
    try:
        accent = merged["accent"]
        if _lum(accent) < 0.30:
            accent = _lighten(accent, 0.42)
        merged["accent"] = accent
        merged["on_accent"] = "#121316" if _lum(accent) > 0.55 else "#f4f5f7"
    except (ValueError, IndexError):
        merged["on_accent"] = "#f4f5f7"
    # Klares Häkchen auf der angehakten Box: nur eine farbige Fläche ist bei sehr
    # dunklen/aufgehellten Akzenten kaum als „an" erkennbar (Damien sah an wie aus).
    # SVG-Häkchen in on_accent als data-URI; fällt ohne QtSvg sauber auf die Fläche zurück.
    _check = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'>"
        f"<path d='M3 7.3 L5.6 9.9 L11 4.2' fill='none' stroke='{merged['on_accent']}' "
        "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/></svg>"
    )
    merged["check_uri"] = "data:image/svg+xml;base64," + \
        base64.b64encode(_check.encode("utf-8")).decode("ascii")
    # Glas-Leisten (immersiv): Leisten/Eingabe translucent, damit das Fenster-
    # Wallpaper (vom _FramelessHost gemalt) hinter Tabs/Adressleiste/Status/Rail
    # durchscheint. Aus → solide wie früher.
    if glass_chrome:
        # Durchsichtigkeit-Slider 0–100 → Alpha 0.85 (opak) … 0.25 (sehr transparent).
        a = round(0.85 - max(0, min(100, chrome_alpha)) / 100 * 0.60, 3)
        ra, ga, ba = _rgb(merged["bg_alt"])
        re_, ge_, be_ = _rgb(merged["bg_elevated"])
        merged["bar_bg"] = f"rgba({ra}, {ga}, {ba}, {a})"
        merged["input_bg"] = f"rgba({re_}, {ge_}, {be_}, {round(min(a + 0.06, 0.95), 3)})"
    else:
        merged["bar_bg"] = merged["bg_alt"]
        merged["input_bg"] = merged["bg_elevated"]
    qss = _QSS.safe_substitute(merged)
    if glossy:
        qss += _glossy_qss(merged)
    extra = theme.get("extra_qss")
    if extra:
        qss += "\n" + str(extra)
    return qss
