"""Eigene, schlichte Line-Icons per QPainter gezeichnet.

Vorteil gegenüber QStyle.standardIcon (die auf Windows altbacken aussehen):
sie werden in der aktuellen Theme-Farbe gezeichnet, sind also auf jedem
Theme konsistent und nicht an den OS-Stil gebunden.
"""

import math

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath

_S = 40  # interne Zeichengröße; QIcon skaliert sauber auf die Toolbar-Größe


def _canvas():
    pm = QPixmap(_S, _S)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def _stroke(p, color, width=3.0):
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _arrow(color, flip=False) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color)
    s = _S
    if flip:
        p.translate(s, 0)
        p.scale(-1, 1)
    p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5))
    head = QPainterPath()
    head.moveTo(s * 0.46, s * 0.34)
    head.lineTo(s * 0.28, s * 0.5)
    head.lineTo(s * 0.46, s * 0.66)
    p.drawPath(head)
    p.end()
    return QIcon(pm)


def back_icon(color) -> QIcon:
    return _arrow(color, flip=False)


def forward_icon(color) -> QIcon:
    return _arrow(color, flip=True)


def reload_icon(color) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color)
    s = _S
    cx, cy, r = s * 0.5, s * 0.52, s * 0.23
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    start_deg, span_deg = 70, 300
    p.drawArc(rect, int(start_deg * 16), int(span_deg * 16))
    # Pfeilspitze am Bogenstart, entlang der Tangente (Drehrichtung CCW)
    a = math.radians(start_deg)
    px, py = cx + r * math.cos(a), cy - r * math.sin(a)
    tan = math.radians(start_deg + 90)
    tx, ty = math.cos(tan), -math.sin(tan)
    nx, ny = math.cos(a), -math.sin(a)
    L = s * 0.12
    tip = QPointF(px + tx * L * 0.5, py + ty * L * 0.5)
    b1 = QPointF(px - tx * L * 0.5 + nx * L * 0.6, py - ty * L * 0.5 + ny * L * 0.6)
    b2 = QPointF(px - tx * L * 0.5 - nx * L * 0.6, py - ty * L * 0.5 - ny * L * 0.6)
    head = QPainterPath()
    head.moveTo(b1)
    head.lineTo(tip)
    head.lineTo(b2)
    p.drawPath(head)
    p.end()
    return QIcon(pm)


def plus_icon(color) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color)
    s = _S
    p.drawLine(QPointF(s * 0.5, s * 0.30), QPointF(s * 0.5, s * 0.70))
    p.drawLine(QPointF(s * 0.30, s * 0.5), QPointF(s * 0.70, s * 0.5))
    p.end()
    return QIcon(pm)


def settings_icon(color) -> QIcon:
    """Schieberegler-Symbol (drei Linien mit Knöpfen) – liest sich als Einstellungen."""
    pm, p = _canvas()
    _stroke(p, color, 2.6)
    s = _S
    rows = ((0.32, 0.62), (0.50, 0.38), (0.68, 0.58))
    for y, _kx in rows:
        p.drawLine(QPointF(s * 0.24, s * y), QPointF(s * 0.76, s * y))
    p.setBrush(QColor(color))
    for y, kx in rows:
        p.drawEllipse(QPointF(s * kx, s * y), s * 0.06, s * 0.06)
    p.end()
    return QIcon(pm)


def window_min_icon(color) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color, 2.2)
    s = _S
    p.drawLine(QPointF(s * 0.30, s * 0.52), QPointF(s * 0.70, s * 0.52))
    p.end()
    return QIcon(pm)


def window_max_icon(color) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color, 2.2)
    s = _S
    p.drawRoundedRect(QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40), 3, 3)
    p.end()
    return QIcon(pm)


def window_restore_icon(color) -> QIcon:
    pm, p = _canvas()
    _stroke(p, color, 2.0)
    s = _S
    p.drawRoundedRect(QRectF(s * 0.36, s * 0.28, s * 0.32, s * 0.32), 3, 3)
    p.drawRoundedRect(QRectF(s * 0.30, s * 0.36, s * 0.32, s * 0.32), 3, 3)
    p.end()
    return QIcon(pm)


def gear_icon(color) -> QIcon:
    """Zahnrad für das Einstellungs-Menü."""
    pm, p = _canvas()
    _stroke(p, color, 2.2)
    s = _S
    cx, cy, r = s * 0.5, s * 0.5, s * 0.20
    for k in range(8):
        a = math.radians(k * 45)
        p.drawLine(
            QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r),
            QPointF(cx + math.cos(a) * (r + s * 0.10), cy + math.sin(a) * (r + s * 0.10)),
        )
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.drawEllipse(QPointF(cx, cy), r * 0.42, r * 0.42)
    p.end()
    return QIcon(pm)


def globe_icon(color) -> QIcon:
    """Globus – steht fuer 'Webseite/Galerie oeffnen'."""
    pm, p = _canvas()
    _stroke(p, color, 2.2)
    s = _S
    cx, cy, r = s * 0.5, s * 0.5, s * 0.30
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.drawEllipse(QPointF(cx, cy), r * 0.45, r)
    p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
    p.end()
    return QIcon(pm)


def palette_icon(color) -> QIcon:
    """Maler-Palette (Theme/Farben) – reine Outline."""
    pm, p = _canvas()
    _stroke(p, color, 2.0)
    s = _S
    p.drawEllipse(QRectF(s * 0.20, s * 0.22, s * 0.56, s * 0.50))
    p.drawEllipse(QPointF(s * 0.42, s * 0.60), s * 0.05, s * 0.05)
    for x, y in ((0.40, 0.36), (0.54, 0.33), (0.65, 0.45)):
        p.drawEllipse(QPointF(s * x, s * y), s * 0.04, s * 0.04)
    p.end()
    return QIcon(pm)


def search_icon(color) -> QIcon:
    """Lupe (Suche)."""
    pm, p = _canvas()
    _stroke(p, color, 2.2)
    s = _S
    p.drawEllipse(QPointF(s * 0.44, s * 0.44), s * 0.18, s * 0.18)
    p.drawLine(QPointF(s * 0.58, s * 0.58), QPointF(s * 0.74, s * 0.74))
    p.end()
    return QIcon(pm)


def shield_icon(color) -> QIcon:
    """Schild (Datenschutz) – reine Outline."""
    pm, p = _canvas()
    _stroke(p, color, 2.0)
    s = _S
    path = QPainterPath()
    path.moveTo(s * 0.50, s * 0.20)
    path.lineTo(s * 0.78, s * 0.30)
    path.lineTo(s * 0.78, s * 0.52)
    path.cubicTo(s * 0.78, s * 0.70, s * 0.64, s * 0.78, s * 0.50, s * 0.82)
    path.cubicTo(s * 0.36, s * 0.78, s * 0.22, s * 0.70, s * 0.22, s * 0.52)
    path.lineTo(s * 0.22, s * 0.30)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def gamepad_icon(color) -> QIcon:
    """Controller (Game-Mode) – reine Outline."""
    pm, p = _canvas()
    _stroke(p, color, 2.0)
    s = _S
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.36, s * 0.68, s * 0.30), s * 0.12, s * 0.12)
    p.drawLine(QPointF(s * 0.29, s * 0.51), QPointF(s * 0.41, s * 0.51))
    p.drawLine(QPointF(s * 0.35, s * 0.45), QPointF(s * 0.35, s * 0.57))
    p.drawEllipse(QPointF(s * 0.63, s * 0.47), s * 0.035, s * 0.035)
    p.drawEllipse(QPointF(s * 0.71, s * 0.55), s * 0.035, s * 0.035)
    p.end()
    return QIcon(pm)


def theme_swatch(theme: dict, w: int = 30, h: int = 18) -> QIcon:
    """Mini-Vorschau eines Themes (Hintergrund, Leiste, Akzent, Textzeilen)."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bg = QColor(theme.get("bg", "#111"))
    bg_alt = QColor(theme.get("bg_alt", "#222"))
    accent = QColor(theme.get("accent", "#888"))
    text = QColor(theme.get("text", "#eee"))
    border = QColor(theme.get("border", "#333"))
    p.setPen(QPen(border, 1))
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 4, 4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg_alt)
    p.drawRoundedRect(QRectF(2, 2, w - 4, h * 0.40), 3, 3)
    p.setBrush(accent)
    p.drawEllipse(QPointF(w * 0.18, h * 0.30), h * 0.11, h * 0.11)
    p.setBrush(text)
    p.drawRoundedRect(QRectF(w * 0.32, h * 0.24, w * 0.45, 2), 1, 1)
    p.setBrush(QColor(theme.get("text_dim", "#999")))
    p.drawRoundedRect(QRectF(w * 0.18, h * 0.66, w * 0.6, 2), 1, 1)
    p.drawRoundedRect(QRectF(w * 0.18, h * 0.82, w * 0.4, 2), 1, 1)
    p.end()
    return QIcon(pm)


_PREVIEW_IMG = ("png", "jpg", "jpeg", "webp", "gif", "bmp")


def theme_preview(theme: dict, w: int = 196, h: int = 116, wallpaper: str = None) -> QIcon:
    """Theme-Vorschau (Mini-Browser). Hat das Theme ein Bild-Wallpaper, wird es
    runterskaliert als Hintergrund gezeigt; sonst der einfarbige Mockup."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    bg = QColor(theme.get("bg", "#111"))
    bg_alt = QColor(theme.get("bg_alt", "#222"))
    bg_el = QColor(theme.get("bg_elevated", "#2a2a2a"))
    accent = QColor(theme.get("accent", "#888"))
    text_dim = QColor(theme.get("text_dim", "#999"))
    border = QColor(theme.get("border", "#333"))

    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 6, 6)
    p.setClipPath(clip)

    has_img = False
    if wallpaper:
        ext = wallpaper.lower().rsplit(".", 1)[-1] if "." in wallpaper else ""
        if ext in _PREVIEW_IMG:
            src = QPixmap(wallpaper)
            if not src.isNull():
                sc = src.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                p.drawPixmap((w - sc.width()) // 2, (h - sc.height()) // 2, sc)
                has_img = True

    p.setPen(Qt.PenStyle.NoPen)
    if not has_img:
        p.setBrush(bg)
        p.drawRect(QRectF(0, 0, w, h))
    else:
        # Inhaltsbereich leicht abdunkeln (wie die Startseite)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRect(QRectF(0, h * 0.20, w, h * 0.80))

    # Chrome: Tab-Leiste, aktiver Tab, Adressleiste
    p.setBrush(bg_alt)
    p.drawRect(QRectF(0, 0, w, h * 0.20))
    p.setBrush(bg_el)
    p.drawRoundedRect(QRectF(8, h * 0.05, w * 0.28, h * 0.16), 4, 4)
    p.setBrush(accent)
    p.drawRect(QRectF(8, h * 0.20 - 2, w * 0.28, 2))
    p.setBrush(bg_el)
    p.drawRoundedRect(QRectF(8, h * 0.26, w - 16, h * 0.12), 6, 6)

    if not has_img:
        # Inhaltszeilen + Akzent-Button nur im einfarbigen Mockup
        p.setBrush(text_dim)
        for i, wd in enumerate((0.55, 0.7, 0.42)):
            p.drawRoundedRect(QRectF(12, h * 0.48 + i * h * 0.10, (w - 24) * wd, 3), 1.5, 1.5)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(12, h * 0.80, w * 0.24, h * 0.10), 4, 4)

    p.setClipping(False)
    p.setPen(QPen(border, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 6, 6)
    p.end()
    return QIcon(pm)


def close_icon(color) -> QIcon:
    """Kleines X für den Tab-Schliessen-Button."""
    pm, p = _canvas()
    _stroke(p, color, 2.4)
    s = _S
    a, b = 0.34, 0.66
    p.drawLine(QPointF(s * a, s * a), QPointF(s * b, s * b))
    p.drawLine(QPointF(s * b, s * a), QPointF(s * a, s * b))
    p.end()
    return QIcon(pm)


def speedometer_icon(color) -> QIcon:
    """Tacho als reine Outline (Zifferblatt-Bogen + Nadel Richtung Anschlag + Nabe)."""
    pm, p = _canvas()
    _stroke(p, color, 2.6)
    s = _S
    cx, cy, r = s * 0.5, s * 0.60, s * 0.30
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    p.drawArc(rect, 0, 180 * 16)  # obere Hälfte = Zifferblatt
    # Tick-Marken an den Enden + Mitte
    for deg in (15, 90, 165):
        a = math.radians(deg)
        x1, y1 = cx + r * math.cos(a), cy - r * math.sin(a)
        x2, y2 = cx + r * 0.82 * math.cos(a), cy - r * 0.82 * math.sin(a)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    # Nadel Richtung Anschlag (oben-rechts)
    a = math.radians(38)
    p.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.80 * math.cos(a), cy - r * 0.80 * math.sin(a)))
    # Nabe (Outline)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), s * 0.045, s * 0.045)
    p.end()
    return QIcon(pm)
