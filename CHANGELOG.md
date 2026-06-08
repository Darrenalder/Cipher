# Changelog

Alle nennenswerten Änderungen an Cipher. Format grob nach [Keep a Changelog](https://keepachangelog.com/de/).

## [0.1.3] — unveröffentlicht

### Neu
- **Data Poisoning (Datenspur verwässern):** Einstellungen → Datenschutz. Schickt in
  **einstellbaren** Abständen (Regler ~15 s bis ~15 min, Standard ~3 min; mit menschlichem
  Jitter aus gelegentlichen Folgesuchen und seltenen längeren Pausen) zufällige Such-Anfragen
  im Hintergrund, um dein Such-Profil mit Rauschen zu verwässern (Idee wie TrackMeNot). Die Anfragen laufen über deine **echte Sitzung**
  (Cookies/Profil) — für die Suchmaschine ununterscheidbar von einer echten Suche, damit sie das
  tatsächliche Profil verwässern statt nur anonymes Rauschen zu erzeugen. Standardmässig aus, im
  Game-Mode pausiert. Ressourcenschonend: die versteckte Seite wird zwischen den Suchen samt
  Renderer-Prozess abgebaut (kein Dauer-RAM/-CPU im Leerlauf). Optionales Test-Ziel (z. B.
  webhook.site) zum Mitverfolgen; jede Anfrage steht im Log (`logs/own-browser.log`)/Konsole.
  Ehrliche Einordnung: Poisoning wirkt nur begrenzt (Profiler filtern Roboter-Rauschen oft
  heraus) — der stärkere Hebel bleibt Prävention (Drittanbieter-Cookies blockiert + Startpage,
  beides aktiv).

## [0.1.2] — 2026-06-08

### Neu
- **Manueller Update-Button:** Einstellungen → Persönlich → „Über Cipher" zeigt jetzt die
  Version und einen Button **„Nach Updates suchen"**. Umgeht die 1×/Tag-Drossel und meldet
  auch „Cipher ist aktuell" bzw. einen Fehler (das automatische Check schweigt in diesen
  Fällen). Der Updater hat dafür zwei neue Signale (`up_to_date`, `check_failed`).

### Behoben
- **Scrollen in den Einstellungen:** Wenn der Mauszeiger beim Scrollen über einem Slider
  oder Dropdown stand, verstellte das Rad den Wert, statt zu scrollen. Jetzt scrollt das
  Rad den Bereich (der Wert ändert sich nur noch, wenn das Element den Fokus hat).
- Update-Dialoge erscheinen jetzt zuverlässig vor dem Einstellungs-Fenster (vorher konnte
  ein modaler Dialog dahinter landen, wenn er aus den Einstellungen ausgelöst wurde).

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
