"""Eigene Tab-Leiste.

- Tabs schrumpfen, je mehr offen sind (Chrome-Stil), bis zu MIN_TAB.
- Ein '+'-Button sitzt immer direkt rechts vom letzten Tab und wandert mit.
- Der Schliess-X wird SELBST gezeichnet (nicht via setTabButton, das lief aus
  dem Tab raus): fixer Abstand von der rechten Tab-Kante, im Tab geclippt.
- X ist bei schmalen Tabs aus, erscheint bei Hover oder am aktiven Tab.
- Mittelklick schliesst einen Tab.
"""

from PyQt6.QtCore import Qt, QSize, QRect, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import QTabBar, QToolButton

MIN_TAB = 52       # untere Breitengrenze
MAX_TAB = 220      # obere Breitengrenze bei wenigen Tabs
SHOW_X_MIN = 80    # X nur dauerhaft sichtbar, wenn Tab breiter als das
X_SIZE = 16        # Kantenlaenge des X-Klickbereichs
X_MARGIN = 8       # fester Abstand X-rechtskante -> Tab-rechtskante


class TabBar(QTabBar):
    plusClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setDocumentMode(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setUsesScrollButtons(False)
        self.setMouseTracking(True)
        self._hover = -1
        self._hover_close = -1
        self._close_color = ""
        self._bg = "#161b22"
        self._bg_sel = "#1f2630"
        self._border = "#2a3142"
        self._glass = False  # Glas-Leisten an → keine solide X-Masken-Füllung (würde als Kasten herausstechen)

        self._plus = QToolButton(self)
        self._plus.setProperty("tabplus", "1")
        self._plus.setText("+")
        self._plus.setFixedSize(28, 28)
        self._plus.setCursor(Qt.CursorShape.ArrowCursor)
        self._plus.setToolTip("Neuer Tab")
        self._plus.clicked.connect(self.plusClicked)

    # --- oeffentlich ------------------------------------------------------
    def set_plus_icon(self, icon) -> None:
        self._plus.setIcon(icon)
        self._plus.setText("")

    def set_glass(self, on: bool) -> None:
        self._glass = bool(on)
        self.update()

    def set_colors(self, theme: dict) -> None:
        self._close_color = theme.get("text", "#ffffff")
        self._bg = theme.get("bg_alt", "#161b22")
        self._bg_sel = theme.get("bg_elevated", "#1f2630")
        self._border = theme.get("border", "#2a3142")
        self.update()

    def relayout(self) -> None:
        self._reposition_plus()
        self.update()

    # --- dynamische Breite ------------------------------------------------
    def tabSizeHint(self, index):
        base = super().tabSizeHint(index)
        count = max(1, self.count())
        avail = self.width() - self._plus.width() - 10
        w = MAX_TAB if avail <= 0 else int(avail / count)
        w = max(MIN_TAB, min(MAX_TAB, w))
        return QSize(w, base.height())

    # --- '+' platzieren ---------------------------------------------------
    def _reposition_plus(self) -> None:
        if self.count() > 0:
            r = self.tabRect(self.count() - 1)
            x = r.right() + 4
            y = r.center().y() - self._plus.height() // 2
        else:
            x, y = 4, (self.height() - self._plus.height()) // 2
        x = max(2, min(x, self.width() - self._plus.width() - 2))
        self._plus.move(x, y)
        self._plus.raise_()
        self._plus.show()

    # --- X-Geometrie / Sichtbarkeit ---------------------------------------
    def _should_show_x(self, i: int) -> bool:
        return (
            self.tabRect(i).width() >= SHOW_X_MIN
            or i == self._hover
            or i == self.currentIndex()
        )

    def _close_rect(self, i: int) -> QRect:
        r = self.tabRect(i)
        x = r.right() - X_MARGIN - X_SIZE
        y = r.center().y() - X_SIZE // 2
        return QRect(x, y, X_SIZE, X_SIZE)

    # --- Zeichnen ---------------------------------------------------------
    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._close_color:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cur = self.currentIndex()
        for i in range(self.count()):
            if not self._should_show_x(i):
                continue
            rect = self._close_rect(i)
            # Text dahinter mit Tab-Farbe maskieren — NUR bei soliden Leisten. Bei
            # Glas-Leisten würde der solide Kasten auf dem transluzenten/verschwommenen
            # Hintergrund als Kasten herausstechen; dann ohne Maske (das Hover-Highlight
            # bzw. die Tab-Verkürzung reichen).
            if not self._glass:
                bg = self._bg_sel if (i == cur or i == self._hover) else self._bg
                p.fillRect(rect.adjusted(-4, -2, 4, 2), QColor(bg))
            # Hover-Highlight auf dem X
            if i == self._hover_close:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self._border))
                p.drawRoundedRect(rect, 4, 4)
            # X
            pen = QPen(QColor(self._close_color))
            pen.setWidthF(2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            a = rect.adjusted(4, 4, -4, -4)
            p.drawLine(a.topLeft(), a.bottomRight())
            p.drawLine(a.topRight(), a.bottomLeft())
        # Pin-Indikator (kleiner Kreis-Umriss links) für angepinnte Tabs
        for i in range(self.count()):
            if self.tabData(i) is True:
                r = self.tabRect(i)
                p.setPen(QPen(QColor(self._close_color), 1.8))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(r.left() + 9, r.center().y()), 3.0, 3.0)
        p.end()

    # --- Events -----------------------------------------------------------
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reposition_plus()
        self.update()

    def mouseMoveEvent(self, e):
        idx = self.tabAt(e.pos())
        hover_close = -1
        if idx >= 0 and self._should_show_x(idx) and self._close_rect(idx).contains(e.pos()):
            hover_close = idx
        if idx != self._hover or hover_close != self._hover_close:
            self._hover = idx
            self._hover_close = hover_close
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover != -1 or self._hover_close != -1:
            self._hover = -1
            self._hover_close = -1
            self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        idx = self.tabAt(e.pos())
        if e.button() == Qt.MouseButton.LeftButton:
            if idx >= 0 and self._should_show_x(idx) and self._close_rect(idx).contains(e.pos()):
                self.tabCloseRequested.emit(idx)
                return
            if idx < 0:  # leerer Bereich -> Fenster ziehen (rahmenlos)
                wh = self.window().windowHandle()
                if wh is not None:
                    wh.startSystemMove()
                    return
        elif e.button() == Qt.MouseButton.MiddleButton:
            if idx >= 0:
                self.tabCloseRequested.emit(idx)
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.tabAt(e.pos()) < 0:
            win = self.window()
            win.showNormal() if win.isMaximized() else win.showMaximized()
            return
        super().mouseDoubleClickEvent(e)
