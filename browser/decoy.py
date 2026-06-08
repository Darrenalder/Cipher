"""Data Poisoning (Obfuscation / „Tracking-Nebel").

Schickt in unregelmaessigen Abstaenden zufaellige Suchanfragen im Hintergrund, um die
echte Such-/Datenspur mit Rauschen zu verwaessern (Idee wie TrackMeNot). Jede Aktion wird
per ``log.info`` ausgegeben (Konsole + ``logs/own-browser.log``), damit man SIEHT, dass es
feuert.

Session-Kopplung: Die Anfragen laufen ueber EINE versteckte, wiederverwendete
``QWebEnginePage`` auf dem ECHTEN Profil (``get_profile()`` — dasselbe benannte, persistente
Profil-Objekt, das auch die sichtbaren Tabs nutzen) — also mit den echten Cookies, JS und
Fingerprint. Fuer die Suchmaschine ist das ununterscheidbar von einer echten Suche aus
dieser Session und verwaessert damit das tatsaechliche Nutzerprofil (nicht nur anonymes
Rauschen wie eine eigene, leere Netzwerk-Session). Genau EINE Page gleichzeitig, Ladevorgaenge
werden gedrosselt (eine Anfrage zur Zeit).

Ressourcen (Gaming-Browser, Zero-Overhead-Ziel): Da die Suchen Minuten auseinanderliegen,
wird die Page nach jeder Suche samt Renderer-Prozess wieder abgebaut (``about:blank`` allein
gibt den ``QtWebEngineProcess`` NICHT frei) — zwischen den Suchen also wirklich 0 MB/0 CPU.
Beim naechsten Feuern wird sie neu erzeugt (Renderer-Coldstart, vernachlaessigbar bei
Minuten-Kadenz). Im disabled/Game-Mode ebenfalls abgebaut.

Ehrliche Grenzen: wirkt nur begrenzt — Profiler filtern Roboter-Noise (fehlende Klicks,
robotisches Timing, keine Folgesuchen) oft heraus. Der staerkere Hebel ist Praevention
(Drittanbieter-Cookies blockiert + Startpage als Default, beides aktiv). Die Session-Kopplung
ist das, was Poisoning ueberhaupt Wirkung gibt. Standardmaessig AUS, im Game-Mode pausiert.
"""

import random
from urllib.parse import quote

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage

from .applog import log

# Queries werden KOMBINATORISCH erzeugt: Städte + Sprach-Vorlagen -> viel mehr Varianz als
# eine fixe Liste (und schwerer für einen Profiler als „bekannte Liste" zu erkennen).
# Echte Umlaute/Akzente: wirkt natürlicher; quote() kodiert sie sauber (ü -> %C3%BC).

# Internationale Standorte (werden in die Orts-Vorlagen eingesetzt).
_CITIES = [
    "zürich", "genf", "basel", "bern", "luzern", "berlin", "münchen", "hamburg",
    "wien", "salzburg", "paris", "lyon", "marseille", "nizza", "madrid", "barcelona",
    "valencia", "sevilla", "rom", "mailand", "florenz", "venedig", "neapel", "london",
    "manchester", "edinburgh", "amsterdam", "lissabon", "prag", "istanbul", "athen",
    "new york", "los angeles", "chicago", "toronto", "tokyo", "osaka", "seoul",
    "bangkok", "singapur", "dubai", "sydney", "kapstadt", "rio de janeiro",
]

# Orts-Vorlagen je Sprache ('{}' = Stadt).
_TEMPLATES = {
    "de": ["wetter {}", "hotels in {}", "beste restaurants {}", "flüge nach {}",
           "sehenswürdigkeiten {}", "wochenende in {}", "öffentliche verkehrsmittel {}"],
    "en": ["weather {}", "things to do in {}", "best coffee in {}", "flights to {}",
           "hotels in {}", "what to see in {}", "nightlife {}"],
    "fr": ["météo {}", "que faire à {}", "hôtels {}", "vols pour {}",
           "restaurants {}", "que visiter à {}"],
    "es": ["tiempo en {}", "qué ver en {}", "hoteles en {}", "vuelos a {}",
           "mejores restaurantes {}", "qué hacer en {}"],
    "it": ["meteo {}", "cosa vedere a {}", "hotel {}", "voli per {}",
           "ristoranti {}", "cosa fare a {}"],
}

# Themenbezogene Anfragen ohne Ort, je Sprache.
_STANDALONE = {
    "de": ["python tutorial", "beste kopfhörer", "rezept lasagne", "vitamin d wirkung",
           "grafikkarte vergleich", "besser schlafen", "elektroauto reichweite",
           "gitarre lernen für anfänger", "passwort manager", "monitor 144hz"],
    "en": ["python tutorial", "best wireless earbuds", "lasagna recipe", "how to sleep better",
           "graphics card comparison", "learn guitar", "password manager", "mechanical keyboard",
           "best vpn 2026", "morning routine ideas"],
    "fr": ["recette lasagnes", "meilleurs écouteurs", "apprendre la guitare", "comment mieux dormir",
           "comparatif carte graphique", "gestionnaire de mots de passe", "idées repas rapides"],
    "es": ["receta de lasaña", "mejores auriculares", "aprender guitarra", "cómo dormir mejor",
           "comparativa tarjeta gráfica", "gestor de contraseñas", "rutina de ejercicio"],
    "it": ["ricetta lasagne", "migliori auricolari", "imparare la chitarra", "come dormire meglio",
           "confronto schede video", "gestore password", "ricette veloci"],
}

_LANGS = list(_TEMPLATES.keys())


def _random_query() -> str:
    """Eine zufällige, organisch wirkende Suchanfrage: zufällige Sprache, zu ~60 %
    ortsbezogen (zufälliger Standort), sonst thematisch."""
    lang = random.choice(_LANGS)
    if random.random() < 0.6:
        return random.choice(_TEMPLATES[lang]).format(random.choice(_CITIES))
    return random.choice(_STANDALONE[lang])


class DataPoisoning(QObject):
    """Hintergrund-Rauschen: zufaellige Suchanfragen ueber die echte Profil-Session."""

    def __init__(self, search_url_fn, parent=None):
        super().__init__(parent)
        self._search_url_fn = search_url_fn      # callable -> Such-URL-Template mit '{}'
        self._page: QWebEnginePage | None = None  # versteckte Page auf dem echten Profil (lazy)
        self._loading = False                    # genau eine Anfrage gleichzeitig (Drossel)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire)
        self._load_guard = QTimer(self)          # Watchdog: falls loadFinished nie kommt
        self._load_guard.setSingleShot(True)
        self._load_guard.timeout.connect(self._load_timed_out)
        self._enabled = False
        self._paused = False                     # z. B. waehrend Game-Mode
        self._current_query = ""                 # fuer das Ergebnis-Log
        # Grundabstand (Ø) in Sekunden, konfigurierbar via set_interval (Slider in Settings).
        # Menschlicher Jitter um diesen Wert herum, s. _next_delay_s.
        self._base_s = 180
        self._burst_remaining = 0                # offene Folgesuchen der aktuellen "Session"
        self._count = 0

    # --- oeffentlich ------------------------------------------------------
    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)
        if self._enabled and not self._paused:
            delay = random.randint(8, 15)        # erste Suche bald (Sicht-/Testbarkeit), dann Minuten
            log.info("Data Poisoning: AN (erste Suche in %d s)", delay)
            self._timer.start(delay * 1000)
        else:
            self._timer.stop()
            if not self._enabled:
                self._burst_remaining = 0
                self._teardown_page()            # aus = wirklich aus, Renderer frei
                log.info("Data Poisoning: AUS (nach %d Anfragen)", self._count)

    def set_paused(self, paused: bool) -> None:
        """Pausieren, ohne den Schalter zu aendern (z. B. Game-Mode)."""
        paused = bool(paused)
        if paused == self._paused:
            return
        self._paused = paused
        if self._paused:
            self._timer.stop()
            self._burst_remaining = 0
            self._teardown_page()                # im Game-Mode RAM/CPU komplett freigeben
            if self._enabled:
                log.info("Data Poisoning: pausiert (Game-Mode)")
        elif self._enabled:
            log.info("Data Poisoning: fortgesetzt")
            self._schedule()

    def set_interval(self, base_s: int) -> None:
        """Durchschnittlichen Abstand (Sekunden) setzen (Slider in den Einstellungen).
        Greift sofort: ist der Decoy aktiv, wird die naechste Suche mit dem neuen Wert
        neu geplant, statt den schon laufenden alten Countdown abzuwarten."""
        self._base_s = max(10, int(base_s))
        if self._enabled and not self._paused and self._timer.isActive():
            self._timer.start(self._next_delay_s() * 1000)

    # --- intern -----------------------------------------------------------
    def _next_delay_s(self) -> int:
        """Naechster Abstand in Sekunden — menschlich wirkender Jitter um ``_base_s`` (Ø):
        meist ~base, gelegentlich kurze Folgesuchen (wie eine echte Such-Session mit
        Verfeinerungen), selten eine laengere Abwesenheit. Skaliert mit dem Slider-Wert."""
        base = self._base_s
        if self._burst_remaining > 0:            # Folgesuche der laufenden "Session" -> kurz danach
            self._burst_remaining -= 1
            lo = max(8, base // 12)
            hi = min(120, max(lo + 5, base // 4))
            return random.randint(lo, hi)
        # Primaere Suche: normaler Abstand (~base). Mit 30 % startet sie 1–2 schnelle Folgesuchen
        # (Seeding aendert NICHT diesen Abstand, nur die naechsten) -> ~30 % der Abstaende kurz.
        if random.random() < 0.30:
            self._burst_remaining = random.randint(1, 2)
        if random.random() < 0.12:               # seltener laengere Pause (Abwesenheit)
            return random.randint(base, base * 3)
        return random.randint(max(8, base // 2), max(base, base * 3 // 2))

    def _schedule(self) -> None:
        delay = self._next_delay_s()
        log.info("Data Poisoning: naechste Suche in %d s", delay)
        self._timer.start(delay * 1000)

    def _ensure_page(self) -> QWebEnginePage:
        """Die EINE versteckte Page auf dem echten Profil (lazy erzeugt)."""
        if self._page is None:
            from .profile import get_profile     # lazy: erzwingt das Profil nicht beim Import
            self._page = QWebEnginePage(get_profile(), self)
            self._page.loadFinished.connect(self._on_load_finished)
        return self._page

    def _fire(self) -> None:
        if not self._enabled or self._paused:
            return
        if self._loading:                        # vorige Anfrage noch offen -> nicht stapeln
            log.info("Data Poisoning: vorige Suche laeuft noch, ueberspringe")
            self._schedule()
            return
        query = _random_query()
        try:
            url = self._search_url_fn().format(quote(query))
        except Exception as e:  # noqa: BLE001 - defensiv, soll nie crashen
            log.warning("Data Poisoning: Such-URL fehlerhaft (%s)", e)
            self._schedule()
            return
        self._count += 1
        self._current_query = query
        self._loading = True
        log.info("Data Poisoning #%d: suche '%s'  ->  %s", self._count, query, url)
        self._ensure_page().setUrl(QUrl(url))    # echte Session: Cookies/JS/Fingerprint
        self._load_guard.start(45000)            # Notbremse, falls loadFinished ausbleibt
        self._schedule()                         # naechste planen (unabhaengig vom Ergebnis)

    def _on_load_finished(self, ok: bool) -> None:
        if self._page is None:
            return
        url = self._page.url().toString()
        if url.startswith("about:"):             # das Leeren (about:blank) selbst ignorieren
            return
        self._load_guard.stop()
        log.info("Data Poisoning: '%s' -> geladen=%s (%s)", self._current_query, ok, url)
        self._loading = False
        # Kurz warten (Folge-/XHR-Requests der Suche noch durchlassen -> wirkt echter), dann
        # Page samt Renderer abbauen -> 0 RAM bis zur naechsten Suche.
        QTimer.singleShot(2500, self._release_page)

    def _release_page(self) -> None:
        """Nach Abschluss einer Suche den Renderer-Prozess komplett freigeben."""
        if not self._loading:                    # nicht mitten in einer neuen Anfrage abbauen
            self._teardown_page()

    def _load_timed_out(self) -> None:
        """loadFinished blieb aus (Netzwerk-Haenger) -> Zustand zuruecksetzen, Renderer frei."""
        if self._loading:
            log.warning("Data Poisoning: '%s' -> Timeout, breche ab", self._current_query)
            self._teardown_page()

    def _teardown_page(self) -> None:
        """Versteckte Page samt Renderer-Prozess abbauen. Laeuft nach JEDER Suche
        (``_release_page``) sowie bei disabled/Game-Mode — beruehrt daher KEIN
        Scheduling-State (Burst-Zaehler) ausser dem reinen Lade-Zustand."""
        self._load_guard.stop()
        if self._page is not None:
            # QWebEnginePage hat KEIN stop() -> laufenden Ladevorgang per WebAction abbrechen.
            self._page.triggerAction(QWebEnginePage.WebAction.Stop)
            self._page.deleteLater()
            self._page = None
        self._loading = False
