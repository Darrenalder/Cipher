# Cipher

Ein gaming-orientierter Privacy-Browser auf **PyQt6 + QtWebEngine** (Chromium ohne
Google-Schicht). Fokus: wenig RAM bei vielen Tabs, keine UI-Freezes, aggressives
Tab-Management — und ein eigenes, immersives Glas-Design.

> Hinweis: Der Projektordner heisst aus historischen Gründen noch `Own Browser`,
> die App selbst ist **Cipher**.

## Features

- **Tab-Management:** Tab-Sleeping (Hintergrund-Tabs nach 30 s `Frozen`, nach 10 min
  `Discarded` → RAM frei), **Game-Mode** (friert alle Hintergrund-Tabs sofort ein),
  Ausnahmen für angepinnte/Audio-Tabs, **RAM-Limiter** (Slider, verwirft Hintergrund-Tabs
  ab Schwelle), Prozess-Limit via Chromium-Flags.
- **Privacy:** Drittanbieter-Cookies geblockt, Startpage als Standardsuche, keine
  Telemetrie (die Google-Schicht von Chrome wird gar nicht erst gebaut).
- **Immersives Design:** rahmenloses Fenster, Wallpaper hinter Tabs/Adressleiste/Leisten,
  **Glas-/Frost-Optik** auf Startseite und Chrome (Frost/Kante/Tiefe + Leisten-Glas
  einstellbar).
- **Eigene Startseite** (`app://newtab`): Uhr, Suchfeld, Speed-Dial, themed Hintergrund
  (Bild/GIF/Video oder eingebaute Canvas-Animationen).
- **Themes:** JSON-Format, live umschaltbar (Einstellungen → Themen), 12+ Presets,
  **Vivaldi-Theme-Import**, Bild-/Video-/Animations-Wallpaper.
- **Einstellungs-Fenster:** Darstellung, Webseiten, Suche, Datenschutz, Leistung, Themen.
- **Auto-Update** über GitHub Releases.

## Starten (aus dem Quellcode)

```bat
run.bat
```

oder mit Konsole zum Debuggen:

```bat
.venv\Scripts\python.exe main.py
```

Voraussetzung: eine venv mit `PyQt6`, `PyQt6-WebEngine`, `psutil`.

## Bauen & Installer

Eigenständige `Cipher.exe` + Windows-Installer (kein Python beim Nutzer nötig):
siehe **[BUILD.md](BUILD.md)** — Kurzform:

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller pillow
.venv\Scripts\pyinstaller.exe cipher.spec      # -> dist\Cipher\Cipher.exe
# danach installer.iss mit Inno Setup kompilieren -> Cipher-Setup-x.y.z.exe
```

## Themes

Jedes Theme ist eine JSON-Datei in `themes/`, live umschaltbar (Einstellungen → Themen).
Eigenes Theme: Datei kopieren, Farben ändern, „neu laden". Fehlende Felder fallen auf
Standardwerte zurück.

```json
{
  "name": "Mein Theme",
  "accent": "#00e5d0",
  "bg": "#0f1216",
  "bg_alt": "#161b22",
  "bg_elevated": "#1f2630",
  "text": "#e6e9ef",
  "text_dim": "#8b93a7",
  "border": "#2a3142",
  "danger": "#ff4d6d",
  "wallpaper": "bild.jpg",
  "wallpaper_dim": 0.4
}
```

`wallpaper` kann ein Bild/GIF/Video (`themes/…`) sein, alternativ `"animation": "aurora"`
(auch `stars`/`matrix`/u. a.). Optional `"extra_qss"` für rohes Qt-Stylesheet.

## Ehrliche Grenze

Ein *harter* MB-Deckel pro Tab ist nicht möglich — Chromium gibt Embeddern keinen echten
Per-Renderer-Memory-Cap. Hebel ist Freeze/Discard + Prozess-Limit. „Viele Tabs, wenig RAM"
wird gut erreicht, aber nicht als garantiertes Limit. Keine Chrome-Erweiterungen
(QtWebEngine unterstützt sie nicht) — Ad-/Tracker-Blocking später über einen
Request-Interceptor.

## Lizenz

GPL v3 — Cipher nutzt PyQt6 (GPL). Quellcode siehe dieses Repository. Details in
[LICENSE](LICENSE).
