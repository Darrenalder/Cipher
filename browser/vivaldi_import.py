"""Vivaldi-Theme-Import.

Vivaldi-Themes sind offenes JSON (im Gegensatz zu Opera GX). Export aus der
Galerie/Browser ist eine `.zip` mit einer settings-JSON + optional einem
Hintergrundbild. Felder: colorAccentBg / colorBg / colorFg / colorWindowBg /
colorHighlightBg / radius / backgroundImage.

Mapping auf unser Format:
  accent      <- colorAccentBg (fallback colorHighlightBg)
  text        <- colorFg
  bg          <- colorWindowBg (Fenster-Basis; fallback colorBg)
  bg_alt      <- colorBg (Toolbar/Tabs)
  bg_elevated <- colorBg, Richtung Hell/Dunkel je nach Luminanz aufgehellt
  border      <- Mischung bg_alt/text
  text_dim    <- Mischung text/bg_alt
  radius      <- radius (in unsere 0..24-Spanne geklemmt)
  wallpaper   <- backgroundImage (aus dem Zip extrahiert, fuer die Startseite)
"""

import json
import re
import zipfile
from pathlib import Path

WHITE, BLACK = "#ffffff", "#000000"


def _rgb(hexstr: str):
    s = str(hexstr).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _mix(c1: str, c2: str, t: float) -> str:
    a, b = _rgb(c1), _rgb(c2)
    return _hex(*(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def _lum(c: str) -> float:
    r, g, b = _rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def vivaldi_to_theme(data: dict) -> dict:
    accent = data.get("colorAccentBg") or data.get("colorHighlightBg") or "#d33b4d"
    text = data.get("colorFg") or "#eaeaea"
    bg = data.get("colorWindowBg") or data.get("colorBg") or "#15151a"
    bg_alt = data.get("colorBg") or bg
    lift = WHITE if _lum(bg) < 0.5 else BLACK
    theme = {
        "name": data.get("name") or "Vivaldi-Theme",
        "accent": accent,
        "bg": bg,
        "bg_alt": bg_alt,
        "bg_elevated": _mix(bg_alt, lift, 0.08),
        "text": text,
        "text_dim": _mix(text, bg_alt, 0.45),
        "border": _mix(bg_alt, text, 0.20),
        "danger": "#ff5d6c",
    }
    if isinstance(data.get("radius"), (int, float)):
        theme["radius"] = max(0, min(24, int(round(data["radius"]))))
    return theme


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "vivaldi-theme"


def import_vivaldi(path, themes_dir: Path) -> str:
    """Liest ein Vivaldi-Theme (.zip oder .json), schreibt unser themes/<slug>.json
    (+ ggf. Wallpaper) und liefert den Theme-Namen zurueck."""
    path = Path(path)
    themes_dir = Path(themes_dir)
    bg_bytes = None
    bg_suffix = ""

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            json_name = next((n for n in names if n.lower().endswith(".json")), None)
            if json_name is None:
                raise ValueError("Keine JSON-Datei im Zip gefunden.")
            data = json.loads(z.read(json_name).decode("utf-8"))
            bg_file = data.get("backgroundImage")
            if bg_file:
                match = next((n for n in names if Path(n).name == bg_file), None)
                if match:
                    bg_bytes = z.read(match)
                    bg_suffix = Path(bg_file).suffix
    else:
        data = json.loads(path.read_text(encoding="utf-8"))

    if "colorAccentBg" not in data and "colorBg" not in data:
        raise ValueError("Das sieht nicht nach einem Vivaldi-Theme aus.")

    theme = vivaldi_to_theme(data)
    slug = _slug(theme["name"])

    if bg_bytes is not None:
        wallpaper = f"{slug}-bg{bg_suffix or '.jpg'}"
        (themes_dir / wallpaper).write_bytes(bg_bytes)
        theme["wallpaper"] = wallpaper
        theme["wallpaper_dim"] = 0.4

    (themes_dir / f"{slug}.json").write_text(
        json.dumps(theme, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return theme["name"]
