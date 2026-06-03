# Changelog

Alle nennenswerten Änderungen an Cipher. Format grob nach [Keep a Changelog](https://keepachangelog.com/de/).

## [0.1.1] — 2026-06-03

### Behoben
- **Flackern beim Start:** Die Theme-Karten erschienen beim Aufbau kurz als eigene Fenster
  (elternlose Widgets, ~1 pro Theme), und die Startseite lud mehrfach hintereinander.
  Jetzt baut sich alles in einem sauberen Durchgang auf — kein Aufflackern mehr.
- **Glas-Frost auf Startseite:** Suchleiste + Speed-Dial zeigten den Wallpaper-Blur glatter
  als die Leisten (Chromium skalierte das Bild nach). Jetzt wird der Frost auf die exakte
  Anzeige-Grösse gerendert und 1:1 angezeigt → gleiche körnige Textur wie Tabs/Adressleiste.
  Ausserdem ist die Blur-Ebene jetzt voll deckend (vorher schimmerte der scharfe Hintergrund
  durch = leichtes Doppelbild/„Durchsichtigkeit").
- **Tab-Schliessen-X:** hatte bei Glas-Leisten einen sichtbaren soliden Kasten dahinter
  (die Text-Maske passte nur zum soliden Hintergrund). Bei Glas-Leisten jetzt ohne Kasten.

### Neu
- **Einstellungen → Persönlich:** Name für die Begrüssung der Startseite + Zeitzone
  (für Uhr & Datum, Standard „Automatisch (System)").
- **Erststart-Menü:** Beim allerersten Start fragt Cipher nach Name und Zeitzone.
- Die Begrüssung zeigt jetzt deinen Namen statt eines festen Werts.
- **Animierter Frost (GIF-Wallpaper):** neues Dropdown unter Einstellungen → Effekte.
  Steuert, wie der Glas-Frost mit einem bewegten GIF-Hintergrund umgeht:
  - *Statisch (sparsam)* — Frost bleibt Frame-1, nur der Voll-Hintergrund animiert (Standard).
  - *Noise-Glas (flüssig)* — Glas zeigt das live-GIF + Noise/Tönung, kein Blur (billig, animiert).
  - *Echter Blur (Qualität)* — Glas zeigt das live-GIF mit GPU-Blur (animiert, höhere Last).
  Die Leisten bleiben in allen Modi statisch (Frame-1) — bewegter Frost in den schmalen
  Leisten kostet CPU und ist kaum sichtbar. Betrifft nur GIF-Wallpaper; statische Bilder
  unverändert (Pixel-Lock-Frost).

### Geändert
- Die beiden „Frost (Milchglas)"-Slider (Startseiten-Glas + Glas-Leisten) heissen
  jetzt **„Verschwommenheit"**.
- **Einstellungen scrollen:** Jede Einstellungs-Sektion (ausser Themen, die schon
  scrollt) sitzt jetzt in einem Scrollbereich. Bei kleinem Fenster scrollt der Inhalt,
  statt sich zu stauchen/überlappen.

## [0.1.0] — 2026-06-03

### Erste Veröffentlichung
- Tab-Sleeping (Freeze nach 30 s, Discard nach 10 min), Game-Mode, RAM-Limiter,
  Prozess-Limit.
- Privacy-Profil: Drittanbieter-Cookies geblockt, Startpage als Standardsuche, keine
  Telemetrie.
- Immersives Glas-Design: Wallpaper hinter Tabs/Adressleiste/Leisten, Frost auf Startseite
  und Chrome (einstellbar).
- Eigene Startseite (`app://newtab`): Uhr, Suche, Speed-Dial, themed Hintergrund.
- JSON-Theme-System, live umschaltbar, mit Vivaldi-Theme-Import.
- Auto-Update über GitHub Releases.
