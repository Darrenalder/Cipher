"""Hauptfenster.

Layout von oben nach unten: Tab-Leiste, Adressleiste, dann der Inhaltsbereich
(Webview-Stack | ausfahrendes Panel | feste Icon-Rail).

Tab-Leiste und Inhalt sind bewusst NICHT als QTabWidget gebaut, sondern als
getrennte QTabBar + QStackedWidget – nur so lässt sich die Adressleiste
zwischen Tabs und Inhalt platzieren.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import psutil
from PyQt6.QtCore import (
    Qt,
    QUrl,
    QTimer,
    QSettings,
    QSize,
    QRect,
    QPoint,
    QEvent,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QShortcut, QDesktopServices, QColor, QImage, QPainter, QPixmap,
    QRegion,
)
from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTabBar,
    QToolBar,
    QToolButton,
    QLineEdit,
    QLabel,
    QMenu,
    QComboBox,
    QSlider,
    QCheckBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QGridLayout,
)

from .tab import BrowserTab
from .tabbar import TabBar
from .sleeper import TabSleeper
from .profile import (
    get_profile,
    get_search_url,
    set_search_engine,
    set_block_third_party,
    SEARCH_ENGINES,
)
from .theming import load_themes, build_qss, THEMES_DIR, BUILTIN_THEME_NAMES
from PyQt6.QtWebEngineCore import QWebEngineSettings
from .newtab import get_handler
from .vivaldi_import import import_vivaldi
from .applog import log
from .updater import Updater, download_and_launch
from .version import __version__
from .icons import (
    back_icon,
    forward_icon,
    reload_icon,
    plus_icon,
    settings_icon,
    speedometer_icon,
    globe_icon,
    gear_icon,
    palette_icon,
    gamepad_icon,
    search_icon,
    shield_icon,
    theme_swatch,
    theme_preview,
    close_icon,
    window_min_icon,
    window_max_icon,
    window_restore_icon,
)

HOME = "app://newtab/"
GALLERY = "https://themes.vivaldi.net"
RESIZE_MARGIN = 4


class EdgeGrip(QWidget):
    """Unsichtbarer Rand-/Eck-Streifen, der Maus-Events an der Fensterkante abfängt
    und `startSystemResize` triggert. Liegt im Z-Index ÜBER der QWebEngineView (deren
    natives Child-Window sonst die Events schluckt) → Resize von allen Kanten OHNE
    sichtbaren kind-freien Layout-Rand. Plattformübergreifend, kein WM_NCHITTEST.
    (Ansatz von Gemini.)"""

    def __init__(self, parent, edge, cursor):
        super().__init__(parent)
        self._edge = edge
        self.setCursor(cursor)
        self.setStyleSheet("background: transparent;")  # unsichtbar, fängt aber Maus

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.window().isMaximized():
            wh = self.window().windowHandle()
            if wh is not None:
                wh.startSystemResize(self._edge)
                return
        super().mousePressEvent(e)


def _blur_pixmap(src, frost: float):
    """Frosted-Glass-Blur per Downscale→Upscale (Kawase-/Dual-Filter-Fake über Qt's
    bilineare Skalierung): stark verkleinern (Fast, bricht Details auf) + smooth wieder
    hochskalieren = seidenweicher Blur in ~1 ms, ohne QGraphicsBlurEffect/Shader und
    ohne OpenGL-Konflikt mit der WebEngineView (Ansatz von Gemini). frost 0–1."""
    if frost <= 0 or src is None or src.isNull():
        return src
    f = 1.0 + frost * 22.0  # frost 1 → ~1/23 Auflösung = kräftiger Frost
    sw = max(1, int(src.width() / f))
    sh = max(1, int(src.height() / f))
    small = src.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.FastTransformation)
    return small.scaled(src.width(), src.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


class _FramelessHost(QWidget):
    """Zentral-Widget des rahmenlosen Fensters: malt das Wallpaper hinter allem
    (immersiv) und hält die EdgeGrip-Overlays für den Resize (kein sichtbarer Rand)."""

    def __init__(self, win):
        super().__init__()
        self._win = win
        self._wp = None            # Wallpaper-QPixmap (Bild-Themes) oder None
        self._wp_scaled = None     # gecachte cover-skalierte Version
        self._wp_frosted = None    # gecachte geblurrte Variante (Frost auf den Leisten)
        self._bg = QColor("#101216")  # Fallback-Farbe (Animation/einfarbig)
        self._dim = 0.0            # Abdunklung wie das Startseiten-Overlay
        self._frost = 0.0          # Weichzeichnung des Wallpapers hinter dem Chrome (0–1)
        E, C = Qt.Edge, Qt.CursorShape
        self._grips = [
            EdgeGrip(self, E.LeftEdge, C.SizeHorCursor),
            EdgeGrip(self, E.RightEdge, C.SizeHorCursor),
            EdgeGrip(self, E.TopEdge, C.SizeVerCursor),
            EdgeGrip(self, E.BottomEdge, C.SizeVerCursor),
            EdgeGrip(self, E(E.LeftEdge.value | E.TopEdge.value), C.SizeFDiagCursor),
            EdgeGrip(self, E(E.RightEdge.value | E.BottomEdge.value), C.SizeFDiagCursor),
            EdgeGrip(self, E(E.RightEdge.value | E.TopEdge.value), C.SizeBDiagCursor),
            EdgeGrip(self, E(E.LeftEdge.value | E.BottomEdge.value), C.SizeBDiagCursor),
        ]

    def set_background(self, pixmap, color, dim=0.0) -> None:
        """Wallpaper (oder None) + Fallback-Farbe + Abdunklung. Das `dim` matcht das
        Startseiten-Overlay, damit nichts heller heraussticht."""
        self._wp = pixmap
        self._wp_scaled = None
        self._wp_frosted = None
        self._bg = color
        self._dim = max(0.0, min(1.0, float(dim)))
        self.update()

    def set_dim(self, dim) -> None:
        self._dim = max(0.0, min(1.0, float(dim)))
        self.update()

    def set_frost(self, frost) -> None:
        self._frost = max(0.0, min(1.0, float(frost)))
        self._wp_frosted = None  # Cache verwerfen, beim nächsten Paint neu blurren
        self.update()

    def _content_rect(self):
        """Rechteck der Web-View (Inhalt) in Host-Koordinaten — dort bleibt das
        Wallpaper scharf (Frost nur drumherum auf den Leisten)."""
        try:
            st = self._win.stack
            return QRect(st.mapTo(self, QPoint(0, 0)), st.size())
        except Exception:
            return None

    def resizeEvent(self, e):
        self._wp_scaled = None
        self._wp_frosted = None
        w, h, m = self.width(), self.height(), RESIZE_MARGIN
        c = m * 3  # grössere Ecken-Greifzone (diagonaler Cursor)
        g = self._grips
        g[0].setGeometry(0, 0, m, h)            # links
        g[1].setGeometry(w - m, 0, m, h)        # rechts
        g[2].setGeometry(0, 0, w, m)            # oben
        g[3].setGeometry(0, h - m, w, m)        # unten
        g[4].setGeometry(0, 0, c, c)            # oben-links
        g[5].setGeometry(w - c, h - c, c, c)    # unten-rechts
        g[6].setGeometry(w - c, 0, c, c)        # oben-rechts
        g[7].setGeometry(0, h - c, c, c)        # unten-links
        for grip in g:
            grip.raise_()  # über allen Kindern (inkl. WebEngineView) halten
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        if self._wp is not None and not self._wp.isNull():
            if self._wp_scaled is None or self._wp_scaled.size() != self.size():
                self._wp_scaled = self._wp.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
            sc = self._wp_scaled
            x = (sc.width() - self.width()) // 2
            y = (sc.height() - self.height()) // 2
            # Scharfes Wallpaper überall — der Inhalts-Bereich bleibt scharf und wird
            # während Live-Resize sichtbar (die Web-View ist dann kurz ausgeblendet, weil
            # Chromium ihren Inhalt einfriert; der Host zieht smooth nach).
            p.drawPixmap(self.rect(), sc, QRect(x, y, self.width(), self.height()))
            if self._frost > 0:
                # Frost NUR auf die Chrome-Bereiche (ausserhalb der Web-View) → Leisten
                # milchig, Inhalt scharf. Cache bis Frost/Grösse ändert.
                if self._wp_frosted is None:
                    crop = sc.copy(x, y, self.width(), self.height())
                    self._wp_frosted = _blur_pixmap(crop, self._frost)
                content = self._content_rect()
                if content is not None and content.isValid():
                    p.setClipRegion(QRegion(self.rect()).subtracted(QRegion(content)))
                p.drawPixmap(self.rect(), self._wp_frosted)
                p.setClipping(False)
            if self._dim > 0:
                p.fillRect(self.rect(), QColor(0, 0, 0, round(self._dim * 255)))
        else:
            p.fillRect(self.rect(), self._bg)
        p.end()


class _ResizeCover(QWidget):
    """Deckt während Live-Resize NUR den Inhalts-Bereich mit dem nativ gemalten, scharfen
    Wallpaper ab → smoother Hintergrund, während Chromium nachzieht. Die Web-View bleibt
    SICHTBAR darunter (rendert weiter, kein `hide()` → kein Native-Window-Abbau, kein
    rAF-Throttle), wird nur kurz verdeckt (Ansatz von Gemini). Malt deckungsgleich zum
    Host (gleiches `_wp_scaled`, gleicher Offset+Dim) → unsichtbarer Übergang."""

    def __init__(self, host):
        super().__init__(host)
        self._host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def paintEvent(self, e):
        h = self._host
        p = QPainter(self)
        sc = getattr(h, "_wp_scaled", None)
        if sc is None or sc.isNull():
            p.fillRect(self.rect(), getattr(h, "_bg", QColor("#101216")))
            p.end()
            return
        off = self.pos()  # Position im Host = Inhalts-Rechteck-Ecke
        x = (sc.width() - h.width()) // 2 + off.x()
        y = (sc.height() - h.height()) // 2 + off.y()
        p.drawPixmap(self.rect(), sc, QRect(x, y, self.width(), self.height()))
        if h._dim > 0:
            p.fillRect(self.rect(), QColor(0, 0, 0, round(h._dim * 255)))
        p.end()


class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cipher")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1280, 800)
        self.setMinimumSize(640, 480)

        self.cfg = QSettings("OwnBrowser", "OwnBrowser")
        self._radius = int(self.cfg.value("radius", 12))
        self._ram_limit = int(self.cfg.value("ram_limit", 0))  # MB, 0 = aus
        self._glossy = self.cfg.value("glossy", True, type=bool)  # Glanz-Oberfläche
        # Glas-Leisten: Wallpaper scheint hinter Tabs/Adressleiste/Status/Rail durch.
        self._glass_chrome = self.cfg.value("glass_chrome", True, type=bool)
        self._chrome_alpha = int(self.cfg.value("chrome_alpha", 55))  # Durchsichtigkeit
        self._chrome_dim = int(self.cfg.value("chrome_dim", 40))      # Abdunklung
        self._chrome_frost = int(self.cfg.value("chrome_frost", 0))   # Unschärfe der Leisten
        # Glas-Slider (Startseite), je 0–100 → CSS 0–1. Frost = Tönungs-/Milchglas-
        # Stärke (echter backdrop-filter-Blur rendert in QtWebEngine nicht, daher Fake).
        self._glass_frost = int(self.cfg.value("glass_frost", 65))
        self._glass_edge = int(self.cfg.value("glass_edge", 35))
        self._glass_depth = int(self.cfg.value("glass_depth", 45))
        # Glas-Slider lädt die Startseite entprellt neu (Live-JS-Var-Update rendert
        # in dieser QtWebEngine nicht – var() in calc()/rgba() friert ein).
        self._glass_reload_timer = QTimer(self)
        self._glass_reload_timer.setSingleShot(True)
        self._glass_reload_timer.setInterval(220)
        self._glass_reload_timer.timeout.connect(self._reload_newtabs)
        # Live-Resize: Inhalt mit Wallpaper-Overlay verdecken (Host malt smooth mit), nach
        # dem letzten Resize-Event prüfen ob Chromium den neuen Frame fertig hat (Double-
        # rAF-Poll), dann Overlay entfernen → zuckungsfrei. (Web-View bleibt sichtbar →
        # kein Native-Window-Abbau, rAF läuft weiter.)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(110)
        self._resize_timer.timeout.connect(self._ping_render_process)
        self._cover_poll = QTimer(self)
        self._cover_poll.setSingleShot(True)
        self._cover_poll.setInterval(16)
        self._cover_poll.timeout.connect(self._check_render_ready)
        self._cover_poll_count = 0
        # Auto-Update (GitHub Releases): entprosselt 1×/Tag, 6 s nach Start (nicht blockierend).
        self._updater = Updater(self)
        self._updater.update_available.connect(self._on_update_available)
        QTimer.singleShot(6000, self._maybe_check_update)
        self._wp_avg_cache: dict[str, QColor] = {}  # Wallpaper-Durchschnittsfarbe
        self._wp_pixmap_cache: dict[str, QPixmap] = {}  # Wallpaper als Fenster-Bg
        self._search_engine = self.cfg.value("search_engine", "Startpage")
        self._block_3p = self.cfg.value("block_third_party_cookies", True, type=bool)
        self._js_enabled = self.cfg.value("javascript_enabled", True, type=bool)
        self._default_zoom = int(self.cfg.value("default_zoom", 100))

        # Themes laden + gespeicherte Auswahl bestimmen.
        self._themes = load_themes()
        saved = self.cfg.value("theme", "Neon Cyan")
        self._current_theme = saved if saved in self._themes else next(iter(self._themes))
        self._settings_win = None
        get_handler().set_theme(self._themes[self._current_theme])

        # Getrennte Tab-Leiste (schrumpfend, mit eigenem '+') + Inhalts-Stack.
        self.tabbar = TabBar()
        self.tabbar.currentChanged.connect(self.on_tab_changed)
        self.tabbar.tabMoved.connect(self._on_tab_moved)
        self.tabbar.tabCloseRequested.connect(self.close_tab)
        self.tabbar.plusClicked.connect(lambda: self.add_tab(HOME))
        self.tabbar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabbar.customContextMenuRequested.connect(self._tab_menu)
        self.stack = QStackedWidget()
        # Transparent, damit beim Ausblenden der Web-View (Live-Resize) der vom Host
        # gemalte Wallpaper-Inhalt durchscheint statt eines opaken dunklen Blocks. Die
        # sichtbare Web-View ist opak und deckt den Stack normal ab → keine Nebenwirkung.
        self.stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.stack.setStyleSheet("background: transparent;")

        self.sleeper = TabSleeper(self.stack, self)
        get_profile().downloadRequested.connect(self._on_download)
        set_search_engine(self._search_engine)
        set_block_third_party(self._block_3p)
        get_profile().settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, self._js_enabled
        )

        # Bestandteile bauen.
        self._build_window_controls()
        self.rail = self._build_rail()
        self.toolbar = self._build_toolbar()
        self._build_statusbar()
        self._settings_win = self._build_settings_window()

        # Zusammenbau (rahmenlos): Rand = Resize-Zone.
        central = _FramelessHost(self)
        central.setObjectName("FramelessHost")
        self._root = QVBoxLayout(central)
        # Kein kind-freier Rand mehr (randlos) — Resize läuft über EdgeGrip-Overlays.
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Oberste Zeile: Tabs (dehnbar) + Fenster-Buttons rechts.
        topbar = QWidget()
        topbar.setObjectName("Topbar")
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        tl.addWidget(self.tabbar, 1)
        tl.addWidget(self._btn_min)
        tl.addWidget(self._btn_max)
        tl.addWidget(self._btn_close)
        self._root.addWidget(topbar)

        self._root.addWidget(self.toolbar)

        body = QWidget()
        body.setObjectName("Body")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self.stack, 1)
        bl.addWidget(self.rail, 0)
        self._root.addWidget(body, 1)
        self._root.addWidget(self._statusbar)
        self.setCentralWidget(central)

        # Qt-Bug (forum.qt.io/topic/83240): bei dünnem Resize-Rand bleibt der
        # Resize-Cursor des _FramelessHost „hängen"; disabled-Buttons zeigen dann
        # den Eltern-Cursor. Fix: EventFilter auf den Chrome-Containern setzt den
        # Host-Cursor zurück, sobald die Maus eintritt (Enter) — das reicht.
        self._host = central
        self._resize_cover = _ResizeCover(central)  # Live-Resize-Overlay (s. resizeEvent)
        for wdg in (topbar, self.toolbar, body, self.rail, self._statusbar, self.tabbar):
            wdg.installEventFilter(self)
        self.urlbar.setCursor(Qt.CursorShape.IBeamCursor)

        self._build_shortcuts()

        self.add_tab(HOME)

        self._proc = psutil.Process()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(2000)
        self._update_status()

        self._populate_theme_combos()
        self._apply_theme(self._current_theme)

    # --- Aufbau -----------------------------------------------------------
    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))

        self.act_back = QAction("Zurück", self)
        self.act_back.triggered.connect(self._go_back)
        tb.addAction(self.act_back)

        self.act_fwd = QAction("Vor", self)
        self.act_fwd.triggered.connect(self._go_forward)
        tb.addAction(self.act_fwd)

        self.act_reload = QAction("Neu laden", self)
        self.act_reload.triggered.connect(self._reload)
        tb.addAction(self.act_reload)

        self.urlbar = QLineEdit()
        self.urlbar.setClearButtonEnabled(True)
        self.urlbar.setPlaceholderText("Adresse eingeben oder suchen …")
        self.urlbar.returnPressed.connect(self.navigate_from_bar)
        tb.addWidget(self.urlbar)

        self.act_game = QAction("Game-Mode", self)
        self.act_game.setToolTip("Game-Mode")
        self.act_game.setCheckable(True)
        self.act_game.toggled.connect(self.toggle_game_mode)
        tb.addAction(self.act_game)

        self._refresh_toolbar_icons(self._themes[self._current_theme]["text"])
        return tb

    def _build_window_controls(self) -> None:
        # Min/Max/Close – sitzen rechts in der Tab-Zeile (siehe __init__-Zusammenbau).
        for attr, extra, slot in (
            ("_btn_min", None, self.showMinimized),
            ("_btn_max", None, self._toggle_max),
            ("_btn_close", "wclose", self.close),
        ):
            b = QToolButton()
            b.setProperty("wctl", "1")
            if extra:
                b.setProperty(extra, "1")
            b.setFixedSize(46, 32)
            b.setIconSize(QSize(16, 16))
            b.clicked.connect(slot)
            setattr(self, attr, b)

    def _refresh_toolbar_icons(self, color: str) -> None:
        self.act_back.setIcon(back_icon(color))
        self.act_fwd.setIcon(forward_icon(color))
        self.act_reload.setIcon(reload_icon(color))
        self.act_game.setIcon(gamepad_icon(color))
        if hasattr(self, "tabbar"):
            self.tabbar.set_plus_icon(plus_icon(color))
        if hasattr(self, "_rail_buttons"):
            self._rail_buttons["performance"].setIcon(speedometer_icon(color))
            self._rail_buttons["appearance"].setIcon(settings_icon(color))
        if hasattr(self, "_gallery_btn"):
            self._gallery_btn.setIcon(globe_icon(color))
        if hasattr(self, "_btn_min"):
            self._btn_min.setIcon(window_min_icon(color))
            self._btn_max.setIcon(
                window_restore_icon(color) if self.isMaximized() else window_max_icon(color)
            )
            self._btn_close.setIcon(close_icon(color))
        if hasattr(self, "settings_btn"):
            self.settings_btn.setIcon(gear_icon(color))

    def _toggle_max(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def eventFilter(self, obj, event):
        # Maus betritt ein Chrome-Widget → hängengebliebenen Resize-Cursor des
        # Hosts zurücksetzen (sonst zeigen ihn disabled-Buttons).
        if event.type() == QEvent.Type.Enter and getattr(self, "_host", None) is not None:
            self._host.setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)

    def changeEvent(self, e) -> None:
        if e.type() == QEvent.Type.WindowStateChange:
            maxd = self.isMaximized()
            for grip in getattr(getattr(self, "_host", None), "_grips", []):
                grip.setVisible(not maxd)  # maximiert: kein Edge-Resize
            if hasattr(self, "_btn_max"):
                col = self._themes[self._current_theme]["text"]
                self._btn_max.setIcon(
                    window_restore_icon(col) if maxd else window_max_icon(col)
                )
        super().changeEvent(e)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        # Erst beim Anzeigen ist das Layout final → Chrome-Insets korrekt messbar. Im
        # __init__ war die Geometrie noch nicht gesetzt (Insets = Müll) → .bg-Naht beim
        # Launch, die bisher erst ein Glas-Toggle behob. Einmal nachmessen + neu laden.
        if not getattr(self, "_did_initial_resync", False):
            self._did_initial_resync = True
            QTimer.singleShot(0, self._resync_immersive)

    def _resync_immersive(self) -> None:
        """Insets neu messen (Layout jetzt fertig) + Startseite damit neu laden, falls
        immersiv. Behebt die Launch-Naht ohne manuelles Glas-Toggle."""
        h = get_handler()
        if h.immersive:
            h.insets = self._content_insets()
            self._reload_newtabs()

    def _maybe_check_update(self) -> None:
        """Höchstens 1×/Tag GitHub Releases prüfen (aus, solange kein Repo konfiguriert)."""
        import time
        try:
            last = float(self.cfg.value("last_update_check", 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if time.time() - last < 86400:
            return
        self.cfg.setValue("last_update_check", time.time())
        self._updater.check()

    def _on_update_available(self, info: dict) -> None:
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setWindowTitle("Update verfügbar")
        box.setText(f"Cipher {info.get('version', '?')} ist verfügbar "
                    f"(installiert: {__version__}).")
        box.setInformativeText("Jetzt herunterladen und aktualisieren?")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        if box.exec() == QMessageBox.StandardButton.Yes:
            if info.get("url"):
                download_and_launch(info["url"], self)
            elif info.get("page_url"):
                self.add_tab(QUrl(info["page_url"]))  # Fallback: Release-Seite öffnen

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._on_live_resize()

    def _on_live_resize(self) -> None:
        """Während Live-Resize friert QtWebEngine ihren Inhalt ein (Chromium rendert erst
        nach dem Resize neu), der Qt-gemalte Host ist dagegen smooth. Für Startseiten-Tabs
        legen wir ein Wallpaper-Overlay über den Inhalt (deckungsgleich zum Host) → smoother
        Hintergrund. Web-View bleibt sichtbar darunter (rendert weiter). Nach dem letzten
        Resize entfernt `_ping_render_process` das Overlay (sobald der Frame fertig ist)."""
        if not getattr(self, "_did_initial_resync", False):
            return  # vor dem ersten Show nicht eingreifen (Aufbau)
        tab = self.stack.currentWidget()
        if (tab is not None and get_handler().immersive
                and tab.url().toString().startswith("app://newtab")):
            self._cover_poll.stop()
            rect = self._host._content_rect()
            if rect is not None and rect.isValid():
                c = self._resize_cover
                c.setGeometry(rect)
                if not c.isVisible():
                    c.show()
                c.raise_()
                c.update()
            self._resize_timer.start()

    def _ping_render_process(self) -> None:
        """Resize beendet. Per Double-rAF warten, bis Chromium den neuen Frame final
        gemalt hat, DANN das Overlay entfernen → kein Zucken (Gemini-Idee). runJavaScript
        wartet aber NICHT auf Promises → Flag im Page setzen + pollen statt Promise."""
        tab = self.stack.currentWidget()
        if tab is None or not tab.url().toString().startswith("app://newtab"):
            self._resize_cover.hide()
            return
        tab.page().runJavaScript(
            "window.__cReady=false;requestAnimationFrame(()=>requestAnimationFrame("
            "()=>{window.__cReady=true;}));")
        self._cover_poll_count = 0
        self._cover_poll.start()

    def _check_render_ready(self) -> None:
        self._cover_poll_count += 1
        tab = self.stack.currentWidget()
        if tab is None or self._cover_poll_count > 20:  # Sicherheits-Timeout ~320 ms
            self._resize_cover.hide()
            return
        tab.page().runJavaScript(
            "window.__cReady===true",
            lambda ok: self._resize_cover.hide() if ok else self._cover_poll.start())

    def _build_statusbar(self) -> None:
        sb = self._statusbar = QStatusBar()
        sb.setSizeGripEnabled(False)

        # Links: Zahnrad-Settings-Menü (unten links) + Status-Info.
        self.settings_btn = QToolButton()
        self.settings_btn.setToolTip("Einstellungen")
        self.settings_btn.setProperty("rail", "1")
        self.settings_btn.setFixedSize(30, 24)
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.clicked.connect(lambda: self._open_settings("appearance"))
        sb.addWidget(self.settings_btn)

        self.status_sleep = QLabel("Tabs: 0")
        sb.addWidget(self.status_sleep)

        # Rechts: Theme-Schnellwahl + Zoom + RAM (in einem Container fuer feste Reihenfolge).
        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self.zoom_reset = QPushButton("Zurücksetzen")
        self.zoom_reset.setToolTip("Zoom auf 100 %")
        self.zoom_reset.clicked.connect(self._reset_zoom)
        rl.addWidget(self.zoom_reset)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(120)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        rl.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(42)
        rl.addWidget(self.zoom_label)

        self.status_ram = QLabel("RAM: …")
        rl.addWidget(self.status_ram)

        self.status_clock = QLabel("--:--")
        rl.addWidget(self.status_clock)

        sb.addPermanentWidget(right)

    def _on_zoom_changed(self, val: int) -> None:
        self.zoom_label.setText(f"{val} %")
        tab = self._current()
        if tab is not None:
            tab.setZoomFactor(val / 100)

    def _reset_zoom(self) -> None:
        self.zoom_slider.setValue(100)

    def _sync_theme_selectors(self, name: str) -> None:
        for cmb in (getattr(self, "cmb_theme", None), getattr(self, "cmb_theme_bar", None)):
            if cmb is not None:
                cmb.blockSignals(True)
                cmb.setCurrentText(name)
                cmb.blockSignals(False)

    def _populate_theme_combos(self) -> None:
        for cmb in (getattr(self, "cmb_theme", None), getattr(self, "cmb_theme_bar", None)):
            if cmb is None:
                continue
            cmb.blockSignals(True)
            cmb.clear()
            cmb.setIconSize(QSize(30, 18))
            for name, theme in self._themes.items():
                cmb.addItem(theme_swatch(theme), name)
            cmb.setCurrentText(self._current_theme)
            cmb.blockSignals(False)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self, activated=lambda: self.add_tab(HOME))
        QShortcut(
            QKeySequence("Ctrl+W"),
            self,
            activated=lambda: self.close_tab(self.tabbar.currentIndex()),
        )
        QShortcut(
            QKeySequence("Ctrl+L"),
            self,
            activated=lambda: (self.urlbar.setFocus(), self.urlbar.selectAll()),
        )
        QShortcut(QKeySequence("F5"), self, activated=self._reload)
        QShortcut(
            QKeySequence("Ctrl+,"),
            self,
            activated=lambda: self._open_settings("appearance"),
        )

    # --- Tabs -------------------------------------------------------------
    def add_tab(self, url=HOME) -> BrowserTab:
        tab = BrowserTab()
        tab.set_create_tab_callback(lambda: self.add_tab(None))
        tab.setZoomFactor(self._default_zoom / 100)
        # Seiten-Hintergrund = Theme-/Wallpaper-Farbton (kein weisses Flackern).
        # NICHT transparent: QtWebEngine rendert eine transparente Web-View schwarz.
        tab.page().setBackgroundColor(self._page_bg_color(self._themes[self._current_theme]))

        index = self.tabbar.count()
        self.stack.insertWidget(index, tab)
        self.tabbar.insertTab(index, "Neuer Tab")
        self.tabbar.setCurrentIndex(index)
        self.tabbar.relayout()

        tab.titleChanged.connect(lambda t, w=tab: self._on_title(w, t))
        tab.urlChanged.connect(lambda u, w=tab: self._on_url(w, u))
        tab.loadFinished.connect(lambda ok, w=tab: self._update_nav(w))

        if url:
            tab.setUrl(QUrl(url))
        return tab

    def close_tab(self, index: int) -> None:
        if index < 0 or index >= self.tabbar.count():
            return
        if self.tabbar.count() <= 1:
            self.add_tab(HOME)  # nie ganz ohne Tab dastehen
        widget = self.stack.widget(index)
        if widget is not None:
            self.stack.removeWidget(widget)
        self.tabbar.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        self.tabbar.relayout()

    def on_tab_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        tab = self.stack.widget(index)
        if tab is None:
            return
        tab.set_foreground()
        self.urlbar.setText(self._display_url(tab.url()))
        self.urlbar.setCursorPosition(0)
        self._update_nav(tab)
        self.tabbar.relayout()
        if hasattr(self, "zoom_slider"):
            z = round(tab.zoomFactor() * 100)
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(z)
            self.zoom_slider.blockSignals(False)
            self.zoom_label.setText(f"{z} %")

    def _on_tab_moved(self, frm: int, to: int) -> None:
        widget = self.stack.widget(frm)
        if widget is None:
            return
        self.stack.removeWidget(widget)
        self.stack.insertWidget(to, widget)
        self.stack.setCurrentIndex(self.tabbar.currentIndex())
        self.tabbar.relayout()

    # --- Navigation -------------------------------------------------------
    def navigate_from_bar(self) -> None:
        text = self.urlbar.text().strip()
        if not text:
            return
        tab = self._current()
        if tab is not None:
            tab.setUrl(QUrl(self._make_url(text)))

    @staticmethod
    def _make_url(text: str) -> str:
        if " " in text or "." not in text:
            return get_search_url().format(quote(text))
        if not text.startswith(("http://", "https://")):
            return "https://" + text
        return text

    def _current(self) -> BrowserTab | None:
        return self.stack.currentWidget()

    def _go_back(self) -> None:
        tab = self._current()
        if tab is not None:
            tab.back()

    def _go_forward(self) -> None:
        tab = self._current()
        if tab is not None:
            tab.forward()

    def _reload(self) -> None:
        tab = self._current()
        if tab is not None:
            tab.reload()

    # --- Reaktionen -------------------------------------------------------
    def _on_title(self, tab: BrowserTab, title: str) -> None:
        index = self.stack.indexOf(tab)
        if index < 0:
            return
        short = title if len(title) <= 24 else title[:23] + "…"
        self.tabbar.setTabText(index, short or "Neuer Tab")

    def _on_url(self, tab: BrowserTab, qurl: QUrl) -> None:
        if tab is self._current():
            self.urlbar.setText(self._display_url(qurl))
            self.urlbar.setCursorPosition(0)
        self._update_nav(tab)

    @staticmethod
    def _display_url(qurl: QUrl) -> str:
        s = qurl.toString()
        return "" if s.startswith("app://newtab") else s

    def _update_nav(self, tab: BrowserTab) -> None:
        if tab is not self._current():
            return
        hist = tab.history()
        self.act_back.setEnabled(hist.canGoBack())
        self.act_fwd.setEnabled(hist.canGoForward())

    # --- Game-Mode --------------------------------------------------------
    def toggle_game_mode(self, on: bool) -> None:
        if on:
            self.sleeper.freeze_after = 5
            self.sleeper.discard_after = 120
            self.sleeper.freeze_all_background()
        else:
            self.sleeper.freeze_after = self.sld_freeze.value()
            self.sleeper.discard_after = self.sld_discard.value() * 60
        if hasattr(self, "chk_game"):
            self.chk_game.blockSignals(True)
            self.chk_game.setChecked(on)
            self.chk_game.blockSignals(False)
        self._update_status()

    # --- Icon-Rail + Einstellungs-Fenster ---------------------------------
    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("PanelRail")
        rail.setFixedWidth(46)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(5, 8, 5, 8)
        rv.setSpacing(6)
        rv.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._rail_buttons = {}
        for key, tip in (("performance", "Performance"), ("appearance", "Aussehen")):
            b = QToolButton()
            b.setToolTip(tip)
            b.setFixedSize(36, 36)
            b.setIconSize(QSize(20, 20))
            b.setProperty("rail", "1")
            b.clicked.connect(lambda _checked=False, k=key: self._open_settings(k))
            rv.addWidget(b)
            self._rail_buttons[key] = b

        # Aktions-Button (kein Panel): oeffnet die Vivaldi-Theme-Galerie.
        self._gallery_btn = QToolButton()
        self._gallery_btn.setToolTip("Vivaldi-Theme-Galerie öffnen")
        self._gallery_btn.setFixedSize(36, 36)
        self._gallery_btn.setIconSize(QSize(20, 20))
        self._gallery_btn.setProperty("rail", "1")
        self._gallery_btn.clicked.connect(lambda: self.add_tab(GALLERY))
        rv.addWidget(self._gallery_btn)

        rv.addStretch(1)
        return rail

    def _section(self, title: str):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(9)
        t = QLabel(title)
        t.setProperty("role", "title")
        v.addWidget(t)
        return w, v

    def _build_performance_section(self) -> QWidget:
        w, v = self._section("Performance")
        lbl = QLabel("Tab-Sleeping")
        lbl.setProperty("role", "section")
        v.addWidget(lbl)

        freeze = int(self.cfg.value("freeze_after", 30))
        discard_min = int(self.cfg.value("discard_after_min", 10))
        self.sleeper.freeze_after = freeze
        self.sleeper.discard_after = discard_min * 60

        self.lbl_freeze = QLabel(f"Einfrieren nach: {freeze} s")
        v.addWidget(self.lbl_freeze)
        self.sld_freeze = QSlider(Qt.Orientation.Horizontal)
        self.sld_freeze.setRange(5, 300)
        self.sld_freeze.setValue(freeze)
        self.sld_freeze.valueChanged.connect(self._on_freeze_changed)
        v.addWidget(self.sld_freeze)

        self.lbl_discard = QLabel(f"Entladen nach: {discard_min} min")
        v.addWidget(self.lbl_discard)
        self.sld_discard = QSlider(Qt.Orientation.Horizontal)
        self.sld_discard.setRange(1, 60)
        self.sld_discard.setValue(discard_min)
        self.sld_discard.valueChanged.connect(self._on_discard_changed)
        v.addWidget(self.sld_discard)

        lbl_lim = QLabel("RAM-Limit")
        lbl_lim.setProperty("role", "section")
        v.addWidget(lbl_lim)
        self.lbl_ramlimit = QLabel(self._ram_limit_text())
        self.lbl_ramlimit.setWordWrap(True)
        v.addWidget(self.lbl_ramlimit)
        self.sld_ramlimit = QSlider(Qt.Orientation.Horizontal)
        self.sld_ramlimit.setRange(0, 4096)
        self.sld_ramlimit.setSingleStep(128)
        self.sld_ramlimit.setPageStep(256)
        self.sld_ramlimit.setValue(self._ram_limit)
        self.sld_ramlimit.valueChanged.connect(self._on_ram_limit_changed)
        v.addWidget(self.sld_ramlimit)

        self.chk_game = QCheckBox("Game-Mode: Hintergrund-Tabs sofort einfrieren")
        self.chk_game.toggled.connect(self._panel_game_toggled)
        v.addWidget(self.chk_game)

        v.addStretch(1)
        return w

    def _build_appearance_section(self) -> QWidget:
        w, v = self._section("Aussehen")
        lbl = QLabel("Theme")
        lbl.setProperty("role", "section")
        v.addWidget(lbl)
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(list(self._themes.keys()))
        self.cmb_theme.setCurrentText(self._current_theme)
        self.cmb_theme.currentTextChanged.connect(self._apply_theme)
        v.addWidget(self.cmb_theme)

        lbl_form = QLabel("Form")
        lbl_form.setProperty("role", "section")
        v.addWidget(lbl_form)
        self.lbl_radius = QLabel(f"Ecken-Rundung: {self._radius} px")
        v.addWidget(self.lbl_radius)
        self.sld_radius = QSlider(Qt.Orientation.Horizontal)
        self.sld_radius.setRange(0, 24)
        self.sld_radius.setValue(self._radius)
        self.sld_radius.valueChanged.connect(self._on_radius_changed)
        v.addWidget(self.sld_radius)

        lbl_fx = QLabel("Effekte")
        lbl_fx.setProperty("role", "section")
        v.addWidget(lbl_fx)

        # Startseiten-Glas: Checkbox + eigene Slider-Gruppe (fährt animiert ein/aus).
        self.chk_glossy = QCheckBox("Startseiten-Glas (Suchleiste + Kacheln)")
        self.chk_glossy.setChecked(self._glossy)
        self.chk_glossy.toggled.connect(self._on_glossy_toggled)
        v.addWidget(self.chk_glossy)
        self._glass_group, gg = self._slider_group()
        self.lbl_gblur, self.sld_gblur = self._glass_slider(
            gg, "Frost (Milchglas)", 0, 100, self._glass_frost)
        self.lbl_gedge, self.sld_gedge = self._glass_slider(gg, "Kante", 0, 100, self._glass_edge)
        self.lbl_gdepth, self.sld_gdepth = self._glass_slider(gg, "Dicke", 0, 100, self._glass_depth)
        v.addWidget(self._glass_group)

        # Glas-Leisten: eigene Checkbox + eigene Slider-Gruppe.
        self.chk_glass_chrome = QCheckBox(
            "Glas-Leisten (Wallpaper hinter Tabs/Adressleiste/Leisten)")
        self.chk_glass_chrome.setChecked(self._glass_chrome)
        self.chk_glass_chrome.toggled.connect(self._on_glass_chrome_toggled)
        v.addWidget(self.chk_glass_chrome)
        self._chrome_group, cg = self._slider_group()
        self.lbl_cfrost, self.sld_cfrost = self._chrome_slider(
            cg, "Frost (Milchglas)", self._chrome_frost)
        self.lbl_calpha, self.sld_calpha = self._chrome_slider(
            cg, "Durchsichtigkeit", self._chrome_alpha)
        self.lbl_cdim, self.sld_cdim = self._chrome_slider(cg, "Abdunklung", self._chrome_dim)
        v.addWidget(self._chrome_group)

        self._glass_group.setVisible(self._glossy)
        self._chrome_group.setVisible(self._glass_chrome)

        v.addStretch(1)
        return w

    def _slider_group(self):
        """Container für eine Slider-Gruppe (lässt sich animiert ein-/ausfahren)."""
        g = QWidget()
        lay = QVBoxLayout(g)
        lay.setContentsMargins(14, 2, 0, 6)
        lay.setSpacing(4)
        return g, lay

    def _chrome_slider(self, layout, name, val):
        lab = QLabel(f"{name}: {val}")
        layout.addWidget(lab)
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        s.setValue(val)
        s.valueChanged.connect(lambda v, n=name, l=lab: l.setText(f"{n}: {v}"))
        s.valueChanged.connect(self._on_chrome_changed)
        layout.addWidget(s)
        return lab, s

    def _slide_group(self, group, show: bool) -> None:
        """Slider-Gruppe per maximumHeight-Animation ein-/ausfahren (Rutsch-Effekt)."""
        anim = QPropertyAnimation(group, b"maximumHeight", self)
        anim.setDuration(240)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        if show:
            group.setMaximumHeight(0)
            group.setVisible(True)
            anim.setStartValue(0)
            anim.setEndValue(group.sizeHint().height())
            anim.finished.connect(lambda: group.setMaximumHeight(16777215))
        else:
            anim.setStartValue(group.height())
            anim.setEndValue(0)
            anim.finished.connect(lambda: group.setVisible(False))
        group._anim = anim  # Referenz halten, sonst Garbage Collection
        anim.start()

    def _on_chrome_changed(self, *_) -> None:
        self._chrome_alpha = self.sld_calpha.value()
        self._chrome_dim = self.sld_cdim.value()
        self._chrome_frost = self.sld_cfrost.value()
        self.cfg.setValue("chrome_alpha", self._chrome_alpha)
        self.cfg.setValue("chrome_dim", self._chrome_dim)
        self.cfg.setValue("chrome_frost", self._chrome_frost)
        # Durchsichtigkeit live ohne Reload: nur QSS (Leisten-Alpha). Frost + Abdunklung
        # live am Host (set_frost/set_dim). Das Startseiten-.bg trägt denselben Dim →
        # entprellt nachladen, sonst dunkelt nur das Chrome ab.
        theme = self._themes.get(self._current_theme, {})
        QApplication.instance().setStyleSheet(build_qss(
            theme, self._radius, self._glossy, self._glass_chrome, self._chrome_alpha))
        h = get_handler()
        if hasattr(self, "_host") and self._glass_chrome:
            self._host.set_dim(self._chrome_dim / 100.0)
            self._host.set_frost(self._chrome_frost / 100.0)
        if h.immersive:
            h.dim_override = self._chrome_dim / 100.0
            self._glass_reload_timer.start()

    def _glass_slider(self, layout, name, lo, hi, val):
        lab = QLabel(f"{name}: {val}")
        layout.addWidget(lab)
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.valueChanged.connect(lambda v, n=name, l=lab: l.setText(f"{n}: {v}"))
        s.valueChanged.connect(self._on_glass_changed)
        layout.addWidget(s)
        return lab, s

    def _glass_css(self) -> tuple:
        """Slider-Ganzzahlen (0–100) → CSS 0–1: (Frost, Kante, Dicke)."""
        return (round(self._glass_frost / 100, 3), round(self._glass_edge / 100, 3),
                round(self._glass_depth / 100, 3))

    def _on_glass_changed(self, *_) -> None:
        self._glass_frost = self.sld_gblur.value()
        self._glass_edge = self.sld_gedge.value()
        self._glass_depth = self.sld_gdepth.value()
        self.cfg.setValue("glass_frost", self._glass_frost)
        self.cfg.setValue("glass_edge", self._glass_edge)
        self.cfg.setValue("glass_depth", self._glass_depth)
        get_handler().glass = self._glass_css()  # neue Tabs/Reloads
        self._glass_reload_timer.start()  # entprellt: lädt Startseite neu (s. __init__)

    def _reload_newtabs(self) -> None:
        """Alle Startseiten-Tabs mit Cache-Buster neu laden (bäckt aktuelle Glas-Werte
        in :root – Live-JS-Update rendert in dieser QtWebEngine nicht)."""
        self._newtab_rev = getattr(self, "_newtab_rev", 0) + 1
        for i in range(self.tabbar.count()):
            tab = self.stack.widget(i)
            if tab is not None and tab.url().toString().startswith("app://newtab"):
                tab.setUrl(QUrl(f"app://newtab/?r={self._newtab_rev}"))

    def _on_glossy_toggled(self, checked: bool) -> None:
        self._glossy = bool(checked)
        self.cfg.setValue("glossy", self._glossy)
        self._apply_theme(self._current_theme)  # Startseite spiegelt den Schalter
        if hasattr(self, "_glass_group"):
            self._slide_group(self._glass_group, self._glossy)  # Slider ein-/ausfahren
        log.info("Startseiten-Glas: %s", "an" if self._glossy else "aus")

    def _on_glass_chrome_toggled(self, checked: bool) -> None:
        self._glass_chrome = bool(checked)
        self.cfg.setValue("glass_chrome", self._glass_chrome)
        self._apply_theme(self._current_theme)  # Leisten translucent/solide + Wallpaper
        if hasattr(self, "_chrome_group"):
            self._slide_group(self._chrome_group, self._glass_chrome)
        log.info("Glas-Leisten: %s", "an" if self._glass_chrome else "aus")

    def _build_themes_section(self) -> QWidget:
        w, v = self._section("Themen")
        # Aktionen oben
        row = QHBoxLayout()
        for label, slot in (
            ("Galerie", lambda: self.add_tab(GALLERY)),
            ("Importieren …", self._import_vivaldi),
            ("Ordner", self._open_themes_dir),
            ("Neu laden", self._reload_themes),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda _checked=False, s=slot: s())
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)

        # Suche
        self._theme_search = QLineEdit()
        self._theme_search.setClearButtonEnabled(True)
        self._theme_search.setPlaceholderText("Themes durchsuchen …")
        self._theme_search.textChanged.connect(self._layout_theme_cards)
        v.addWidget(self._theme_search)

        # Aufklappbare Gruppen: Standard (mitgeliefert) / Erweiterung (importiert)
        host = QWidget()
        hv = QVBoxLayout(host)
        hv.setContentsMargins(0, 8, 0, 0)
        hv.setSpacing(14)
        hv.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._grp_std, self._hdr_std, self._theme_grid_std = self._theme_group("Standard")
        self._grp_ext, self._hdr_ext, self._theme_grid_ext = self._theme_group("Erweiterung")
        hv.addWidget(self._grp_std)
        hv.addWidget(self._grp_ext)
        hv.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        v.addWidget(scroll, 1)
        self._refresh_theme_grid()
        return w

    def _theme_group(self, title: str):
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(6)
        header = QToolButton()
        header.setObjectName("GroupHeader")
        header.setText(title)
        header.setCheckable(True)
        header.setChecked(True)
        header.setArrowType(Qt.ArrowType.DownArrow)
        header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        header.setCursor(Qt.CursorShape.ArrowCursor)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(2, 0, 0, 0)
        grid.setSpacing(12)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.toggled.connect(lambda on, h=header, c=content: self._toggle_group(h, c, on))
        bv.addWidget(header)
        bv.addWidget(content)
        return box, header, grid

    @staticmethod
    def _toggle_group(header, content, on: bool) -> None:
        content.setVisible(on)
        header.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    def _refresh_theme_grid(self) -> None:
        if not hasattr(self, "_theme_grid_std"):
            return
        for grid in (self._theme_grid_std, self._theme_grid_ext):
            while grid.count():
                item = grid.takeAt(0)
                wdg = item.widget()
                if wdg is not None:
                    wdg.deleteLater()
        self._theme_cards = []
        for name, theme in self._themes.items():
            grid = self._theme_grid_std if name in BUILTIN_THEME_NAMES else self._theme_grid_ext
            self._theme_cards.append((name, self._theme_card(name, theme), grid))
        self._layout_theme_cards()

    def _update_active_theme_card(self) -> None:
        """Nur das Aktiv-Highlight umsetzen, ohne das Grid neu zu bauen – sonst
        springt der Scroll hoch und die Karten flackern bei jedem Theme-Wechsel."""
        if not hasattr(self, "_theme_cards"):
            return
        for name, card, _grid in self._theme_cards:
            active = "true" if name == self._current_theme else "false"
            if card.property("active") != active:
                card.setProperty("active", active)
                card.style().unpolish(card)
                card.style().polish(card)

    def _layout_theme_cards(self, *_) -> None:
        if not hasattr(self, "_theme_cards"):
            return
        for grid in (self._theme_grid_std, self._theme_grid_ext):
            while grid.count():
                grid.takeAt(0)
        text = self._theme_search.text().strip().lower() if hasattr(self, "_theme_search") else ""
        if text:  # bei aktiver Suche beide Gruppen aufklappen
            for hdr in (self._hdr_std, self._hdr_ext):
                hdr.setChecked(True)
        cols, std_n, ext_n = 2, 0, 0
        for name, card, grid in self._theme_cards:
            match = (not text) or (text in name.lower())
            card.setVisible(match)
            if not match:
                continue
            if grid is self._theme_grid_std:
                grid.addWidget(card, std_n // cols, std_n % cols)
                std_n += 1
            else:
                grid.addWidget(card, ext_n // cols, ext_n % cols)
                ext_n += 1
        self._grp_std.setVisible(std_n > 0)
        self._grp_ext.setVisible(ext_n > 0)

    def _theme_card(self, name: str, theme: dict) -> QToolButton:
        card = QToolButton()
        card.setObjectName("ThemeCard")
        card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        wp = theme.get("wallpaper")
        wp_path = str(THEMES_DIR / wp) if wp else None
        card.setIcon(theme_preview(theme, wallpaper=wp_path))
        card.setIconSize(QSize(196, 116))
        card.setText(name)
        card.setFixedSize(216, 168)
        card.setProperty("active", "true" if name == self._current_theme else "false")
        card.clicked.connect(lambda _checked=False, n=name: self._apply_theme(n))
        # Löschen-X oben rechts
        x = QToolButton(card)
        x.setProperty("tabclose", "1")
        x.setCursor(Qt.CursorShape.ArrowCursor)
        x.setFixedSize(22, 22)
        x.setIconSize(QSize(13, 13))
        x.setIcon(close_icon(theme["text"]))
        x.setToolTip("Theme löschen")
        x.clicked.connect(lambda _checked=False, n=name: self._delete_theme(n))
        x.move(216 - 28, 6)
        x.raise_()
        return card

    def _delete_theme(self, name: str) -> None:
        from PyQt6.QtWidgets import QMessageBox

        theme = self._themes.get(name)
        if theme is None:
            return
        box = QMessageBox(self._settings_win)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Theme löschen")
        box.setText(f"Theme '{name}' wirklich löschen? Das lässt sich nicht rückgängig machen.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)  # Enter bestätigt
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        path = theme.get("__path__")
        if path:
            try:
                Path(path).unlink(missing_ok=True)
                wp = theme.get("wallpaper")
                if wp:
                    (THEMES_DIR / wp).unlink(missing_ok=True)
            except OSError:
                pass
        self._themes = load_themes()
        if self._current_theme not in self._themes:
            self._current_theme = next(iter(self._themes))
            self._apply_theme(self._current_theme)
        self._populate_theme_combos()
        self._refresh_theme_grid()
        log.info("Theme gelöscht: %s", name)
        self._statusbar.showMessage(f"Theme {name} gelöscht.", 3000)

    def _build_search_section(self) -> QWidget:
        w, v = self._section("Suche")
        lbl = QLabel("Standard-Suchmaschine")
        lbl.setProperty("role", "section")
        v.addWidget(lbl)
        self.cmb_search = QComboBox()
        self.cmb_search.addItems(list(SEARCH_ENGINES.keys()))
        self.cmb_search.setCurrentText(self._search_engine)
        self.cmb_search.currentTextChanged.connect(self._on_search_engine_changed)
        v.addWidget(self.cmb_search)
        hint = QLabel("Gilt für die Adressleiste und das Suchfeld der Startseite.")
        hint.setProperty("role", "section")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addStretch(1)
        return w

    def _build_privacy_section(self) -> QWidget:
        w, v = self._section("Datenschutz & Sicherheit")
        lbl1 = QLabel("Cookies")
        lbl1.setProperty("role", "section")
        v.addWidget(lbl1)
        self.chk_3pcookies = QCheckBox("Drittanbieter-Cookies blockieren (Tracking-Schutz)")
        self.chk_3pcookies.setChecked(self._block_3p)
        self.chk_3pcookies.toggled.connect(self._on_3pcookies_toggled)
        v.addWidget(self.chk_3pcookies)
        lbl2 = QLabel("Browserdaten löschen")
        lbl2.setProperty("role", "section")
        v.addWidget(lbl2)
        for label, slot in (
            ("Cache leeren", self._clear_cache),
            ("Cookies löschen", self._clear_cookies),
            ("Verlauf löschen", self._clear_history),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda _checked=False, s=slot: s())
            v.addWidget(b)
        v.addStretch(1)
        return w

    def _build_webpages_section(self) -> QWidget:
        w, v = self._section("Webseiten")
        lbl1 = QLabel("Standard-Zoom für neue Tabs")
        lbl1.setProperty("role", "section")
        v.addWidget(lbl1)
        self.lbl_defzoom = QLabel(f"Standard-Zoom: {self._default_zoom} %")
        v.addWidget(self.lbl_defzoom)
        self.sld_defzoom = QSlider(Qt.Orientation.Horizontal)
        self.sld_defzoom.setRange(25, 300)
        self.sld_defzoom.setValue(self._default_zoom)
        self.sld_defzoom.valueChanged.connect(self._on_defzoom_changed)
        v.addWidget(self.sld_defzoom)
        lbl2 = QLabel("Inhalt")
        lbl2.setProperty("role", "section")
        v.addWidget(lbl2)
        self.chk_js = QCheckBox("JavaScript aktivieren")
        self.chk_js.setChecked(self._js_enabled)
        self.chk_js.toggled.connect(self._on_js_toggled)
        v.addWidget(self.chk_js)
        v.addStretch(1)
        return w

    def _on_search_engine_changed(self, name: str) -> None:
        self._search_engine = name
        self.cfg.setValue("search_engine", name)
        set_search_engine(name)

    def _on_3pcookies_toggled(self, on: bool) -> None:
        self._block_3p = on
        self.cfg.setValue("block_third_party_cookies", on)
        set_block_third_party(on)

    def _on_defzoom_changed(self, val: int) -> None:
        self._default_zoom = val
        self.lbl_defzoom.setText(f"Standard-Zoom: {val} %")
        self.cfg.setValue("default_zoom", val)

    def _on_js_toggled(self, on: bool) -> None:
        self._js_enabled = on
        self.cfg.setValue("javascript_enabled", on)
        get_profile().settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, on
        )

    def _clear_cache(self) -> None:
        get_profile().clearHttpCache()
        self._statusbar.showMessage("Cache geleert.", 3000)

    def _clear_cookies(self) -> None:
        get_profile().cookieStore().deleteAllCookies()
        self._statusbar.showMessage("Cookies gelöscht.", 3000)

    def _clear_history(self) -> None:
        get_profile().clearAllVisitedLinks()
        self._statusbar.showMessage("Verlauf gelöscht.", 3000)

    def _build_settings_window(self) -> QWidget:
        # Eigenes Fenster (mit normalem Rahmen), an die Hauptfenster-Lebensdauer gekoppelt.
        win = QWidget(self, Qt.WindowType.Window)
        win.setWindowTitle("Own Browser – Einstellungen")
        win.setMinimumSize(720, 480)
        win.resize(840, 560)
        h = QHBoxLayout(win)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        cats = self._settings_cats = QListWidget()
        cats.setObjectName("SettingsCats")
        cats.setFixedWidth(200)
        cats.setIconSize(QSize(18, 18))

        stack = self._settings_stack = QStackedWidget()
        col = self._themes[self._current_theme]["text"]
        pages = (
            ("Darstellung", settings_icon(col), self._build_appearance_section()),
            ("Webseiten", globe_icon(col), self._build_webpages_section()),
            ("Suche", search_icon(col), self._build_search_section()),
            ("Datenschutz", shield_icon(col), self._build_privacy_section()),
            ("Leistung", speedometer_icon(col), self._build_performance_section()),
            ("Themen", palette_icon(col), self._build_themes_section()),
        )
        for title, icon, page in pages:
            QListWidgetItem(icon, title, cats)
            stack.addWidget(page)
        cats.currentRowChanged.connect(stack.setCurrentIndex)
        cats.setCurrentRow(0)

        h.addWidget(cats)
        h.addWidget(stack, 1)
        return win

    def _open_settings(self, category: str = "appearance") -> None:
        if self._settings_win is None:
            self._settings_win = self._build_settings_window()
        row = {
            "appearance": 0,
            "webpages": 1,
            "search": 2,
            "privacy": 3,
            "performance": 4,
            "themes": 5,
        }.get(category, 0)
        self._settings_cats.setCurrentRow(row)
        self._settings_win.show()
        self._settings_win.raise_()
        self._settings_win.activateWindow()

    def _on_freeze_changed(self, val: int) -> None:
        self.lbl_freeze.setText(f"Einfrieren nach: {val} s")
        self.cfg.setValue("freeze_after", val)
        if not self.act_game.isChecked():
            self.sleeper.freeze_after = val

    def _on_discard_changed(self, val: int) -> None:
        self.lbl_discard.setText(f"Entladen nach: {val} min")
        self.cfg.setValue("discard_after_min", val)
        if not self.act_game.isChecked():
            self.sleeper.discard_after = val * 60

    def _ram_limit_text(self) -> str:
        if self._ram_limit <= 0:
            return "RAM-Limit: aus"
        return f"RAM-Limit: {self._ram_limit} MB — drosselt ab ~90 % (verwirft Hintergrund-Tabs)"

    def _on_ram_limit_changed(self, val: int) -> None:
        val = (val // 128) * 128  # auf 128er-Schritte runden, 0 = aus
        self._ram_limit = val
        self.lbl_ramlimit.setText(self._ram_limit_text())
        self.cfg.setValue("ram_limit", val)

    def _on_radius_changed(self, val: int) -> None:
        self._radius = val
        self.lbl_radius.setText(f"Ecken-Rundung: {val} px")
        self.cfg.setValue("radius", val)
        theme = self._themes.get(self._current_theme, {})
        QApplication.instance().setStyleSheet(build_qss(
            theme, val, self._glossy, self._glass_chrome, self._chrome_alpha))

    def _panel_game_toggled(self, on: bool) -> None:
        if self.act_game.isChecked() != on:
            self.act_game.setChecked(on)

    # --- Theming ----------------------------------------------------------
    def _apply_theme(self, name: str) -> None:
        theme = self._themes.get(name)
        if theme is None:
            log.warning("Theme nicht gefunden: %s", name)
            return
        log.info("Theme angewandt: %s", name)
        # Manche (z. B. importierte Vivaldi-) Themes bringen eine eigene Rundung mit.
        if "radius" in theme:
            try:
                self._radius = max(0, min(24, int(theme["radius"])))
                self.cfg.setValue("radius", self._radius)
                if hasattr(self, "sld_radius"):
                    self.sld_radius.blockSignals(True)
                    self.sld_radius.setValue(self._radius)
                    self.sld_radius.blockSignals(False)
                    self.lbl_radius.setText(f"Ecken-Rundung: {self._radius} px")
            except (TypeError, ValueError):
                pass
        QApplication.instance().setStyleSheet(build_qss(
            theme, self._radius, self._glossy, self._glass_chrome, self._chrome_alpha))
        handler = get_handler()
        handler.glossy = self._glossy  # Startseite spiegelt den Glanz-Schalter
        handler.glass = self._glass_css()
        handler.set_theme(theme)
        self._refresh_toolbar_icons(theme["text"])
        self.tabbar.set_colors(theme)  # X/Pin-Farben + Masken-Hintergründe (sonst X unsichtbar)
        # Immersiv = Bild-Wallpaper + Glas-Leisten: das Fenster malt das Wallpaper hinter
        # dem Chrome; die Startseite koppelt ihr .bg an die Fenster-Cover-Skalierung
        # (Insets = Chrome-Höhen) → keine Naht Chrome↔Inhalt. Web-View bleibt opak.
        wp = theme.get("wallpaper")
        is_img = bool(wp) and "." in wp and \
            wp.lower().rsplit(".", 1)[-1] not in ("mp4", "webm", "ogg")
        immersive = self._glass_chrome and is_img
        h = get_handler()
        h.immersive = immersive
        h.insets = self._content_insets() if immersive else (0, 0, 0, 0)
        h.dim_override = (self._chrome_dim / 100.0) if immersive else None
        bgc = self._page_bg_color(theme)
        # Seiten-Hintergrund = Theme-/Wallpaper-Farbton (kein weisses Flackern). NICHT
        # transparent: QtWebEngine rendert eine transparente Web-View schwarz statt das
        # Host-Bild durchscheinen zu lassen.
        for i in range(self.tabbar.count()):
            t = self.stack.widget(i)
            if t is not None:
                t.page().setBackgroundColor(bgc)
        pm = None
        if is_img:
            pm = self._wp_pixmap_cache.get(wp)
            if pm is None:
                pm = QPixmap(str(THEMES_DIR / wp))
                self._wp_pixmap_cache[wp] = pm
        if hasattr(self, "_host"):
            if self._glass_chrome:
                wp_dim = (self._chrome_dim / 100.0) if pm else 0.0
                self._host.set_background(
                    pm if (pm and not pm.isNull()) else None, bgc, wp_dim)
                # Frost = Weichzeichnung des Wallpapers hinter den Leisten (set_background
                # verwirft den Cache, daher danach setzen).
                self._host.set_frost(self._chrome_frost / 100.0 if pm else 0.0)
            else:
                # Solide Leisten → kein Wallpaper hinterm Chrome, einfarbig wie früher.
                self._host.set_background(None, QColor(theme["bg"]), 0.0)
        self._current_theme = name
        self.cfg.setValue("theme", name)
        self._sync_theme_selectors(name)
        # Startseite bei JEDEM Theme-Wechsel neu laden. Eindeutige Cache-Buster-URL,
        # weil das app://-Custom-Schema weder auf reload() noch auf setUrl(gleiche
        # URL) reagiert (Handler-Falle) – nur ein neues ?r= ruft den Handler neu auf.
        self._newtab_rev = getattr(self, "_newtab_rev", 0) + 1
        for i in range(self.tabbar.count()):
            tab = self.stack.widget(i)
            if tab is None or not tab.url().toString().startswith("app://newtab"):
                continue
            tab.setUrl(QUrl(f"app://newtab/?r={self._newtab_rev}"))
        # Nur Highlight umsetzen (kein Grid-Rebuild → kein Scroll-Sprung/Flackern).
        self._update_active_theme_card()

    def _page_bg_color(self, theme: dict) -> QColor:
        """Ladefarbe der Startseite. Bei Bild-Wallpaper die Durchschnittsfarbe des
        Bilds (Reload geht nahtlos ins Wallpaper über), sonst die Theme-bg-Farbe.
        Pro Wallpaper-Datei gecacht (1×1-Smooth-Scale = Mittelwert)."""
        wp = theme.get("wallpaper")
        if wp:
            ext = wp.lower().rsplit(".", 1)[-1] if "." in wp else ""
            if ext not in ("mp4", "webm", "ogg"):  # nur Bilder mitteln, keine Videos
                cached = self._wp_avg_cache.get(wp)
                if cached is None:
                    img = QImage(str(THEMES_DIR / wp))
                    if img.isNull():
                        cached = QColor(theme["bg"])
                    else:
                        cached = img.scaled(
                            1, 1,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        ).pixelColor(0, 0)
                    self._wp_avg_cache[wp] = cached
                return cached
        return QColor(theme["bg"])

    def _content_insets(self) -> tuple:
        """Chrome-Dicken (top, right, bottom, left) in px = wie weit die Web-View vom
        Fensterrand absteht. Damit kann die Startseite ihr .bg auf die FENSTER-Cover-
        Skalierung koppeln (deckungsgleich mit dem Host-Wallpaper → keine Naht). Werte
        sind grössen-unabhängig (Chrome-Höhen sind fix), nur einmal nach Layout gültig."""
        try:
            p = self.stack.mapTo(self, QPoint(0, 0))
            top = max(0, p.y())
            left = max(0, p.x())
            right = max(0, self.width() - (p.x() + self.stack.width()))
            bottom = max(0, self.height() - (p.y() + self.stack.height()))
            # Fallback, falls vor dem ersten Layout (alles 0) aufgerufen.
            if top == 0 and right == 0 and bottom == 0 and left == 0:
                return (86, 46, 30, 0)
            return (top, right, bottom, left)
        except Exception:
            return (86, 46, 30, 0)

    def _open_themes_dir(self) -> None:
        THEMES_DIR.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(THEMES_DIR)))

    def _reload_themes(self) -> None:
        self._themes = load_themes()
        if self._current_theme not in self._themes:
            self._current_theme = next(iter(self._themes))
        self._populate_theme_combos()
        self._apply_theme(self._current_theme)
        # Theme-Menge hat sich geändert (neuer Import) → Grid voll neu bauen.
        self._refresh_theme_grid()

    def _import_vivaldi(self) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            self, "Vivaldi-Theme importieren", "", "Vivaldi-Theme (*.zip *.json)"
        )
        if not path:
            return
        try:
            name = import_vivaldi(path, THEMES_DIR)
        except Exception as exc:  # noqa: BLE001 – Nutzer-Feedback statt Crash
            log.exception("Vivaldi-Import fehlgeschlagen: %s", path)
            QMessageBox.warning(
                self, "Import fehlgeschlagen", f"Konnte das Theme nicht importieren:\n{exc}"
            )
            return
        log.info("Theme importiert: %s", name)
        self._reload_themes()
        if name in self._themes:
            self._apply_theme(name)

    def _on_download(self, item) -> None:
        # Downloads erlauben (sonst bricht QtWebEngine sie ab) -> Downloads-Ordner.
        item.setDownloadDirectory(str(Path.home() / "Downloads"))
        item.accept()
        # Jedes .zip nach Abschluss als moegliches Vivaldi-Theme pruefen.
        if (item.downloadFileName() or "").lower().endswith(".zip"):
            item.isFinishedChanged.connect(lambda it=item: self._maybe_import_theme(it))

    def _maybe_import_theme(self, item) -> None:
        from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

        if item.state() != QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            return
        path = Path(item.downloadDirectory()) / item.downloadFileName()
        try:
            name = import_vivaldi(path, THEMES_DIR)
        except Exception:  # noqa: BLE001 – kein Vivaldi-Theme -> normaler Download
            return
        self._reload_themes()
        if name in self._themes:
            self._apply_theme(name)
        self._statusbar.showMessage(f"Theme {name} importiert und aktiviert.", 5000)

    # --- Tab-Kontextmenue -------------------------------------------------
    def _tab_menu(self, pos) -> None:
        index = self.tabbar.tabAt(pos)
        if index < 0:
            return
        tab = self.stack.widget(index)
        menu = QMenu(self)
        act_pin = menu.addAction("Tab loesen" if tab.pinned else "Tab anheften")
        act_sleep = menu.addAction("Jetzt einschlaefern")
        menu.addSeparator()
        act_close = menu.addAction("Schliessen")
        chosen = menu.exec(self.tabbar.mapToGlobal(pos))
        if chosen == act_pin:
            tab.pinned = not tab.pinned
            self.tabbar.setTabData(index, tab.pinned)
            self.tabbar.update()
            self._on_title(tab, tab.title())
        elif chosen == act_sleep:
            tab.freeze()
        elif chosen == act_close:
            self.close_tab(index)

    # --- Statusleiste -----------------------------------------------------
    @staticmethod
    def _proc_mem(proc) -> int:
        # USS = nur dem Prozess privat zugeordneter Speicher. Verhindert, dass
        # geteilte Pages (DLLs, GPU) in jedem Chromium-Prozess mitgezählt und
        # damit mehrfach addiert werden (sonst entstehen Phantom-Werte).
        try:
            return proc.memory_full_info().uss
        except (psutil.Error, AttributeError):
            try:
                return proc.memory_info().rss
            except psutil.Error:
                return 0

    def _update_status(self) -> None:
        try:
            mem = self._proc_mem(self._proc)
            for child in self._proc.children(recursive=True):
                mem += self._proc_mem(child)
            mem_mb = mem / (1024 * 1024)
        except psutil.Error:
            mem_mb = None

        # RAM-Limit durchsetzen: nahe am Limit Hintergrund-Tabs verwerfen.
        throttled = False
        if mem_mb is not None and self._ram_limit > 0 and mem_mb >= self._ram_limit * 0.9:
            self.sleeper.discard_all_background()
            throttled = True

        if mem_mb is None:
            self.status_ram.setText("RAM: ?")
        else:
            self.status_ram.setText(f"RAM: {mem_mb:,.0f} MB{' (Limit)' if throttled else ''}")

        total = self.tabbar.count()
        sleeping = self.sleeper.sleeping_count()
        mode = "   ·  Game-Mode" if self.act_game.isChecked() else ""
        self.status_sleep.setText(f"Tabs: {total}   schlafend: {sleeping}{mode}")
        self.status_clock.setText(datetime.now().strftime("%H:%M"))
