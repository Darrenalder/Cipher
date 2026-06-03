# Cipher bauen & verpacken (Windows-Installer)

Erzeugt aus dem Quellcode eine eigenständige `Cipher.exe` (kein Python beim Nutzer nötig)
und daraus ein `Cipher-Setup-x.y.z.exe`.

## 0. Einmalig: Werkzeuge installieren

```powershell
# im Projektordner, mit aktivierter venv
.venv\Scripts\python.exe -m pip install pyinstaller pillow
```

- **Pillow** wird nur gebraucht, falls noch keine `assets\icon.ico` existiert (PyInstaller
  konvertiert dann `icon.png` automatisch). Alternativ eine `icon.ico` selbst erzeugen
  (z. B. https://icoconvert.com) und nach `assets\icon.ico` legen.
- **Inno Setup** für den Installer: https://jrsoftware.org/isdl.php (einmalig installieren).

## 1. App bündeln (PyInstaller)

**Schnellweg — ein Befehl baut exe + Installer nach `_build\`** (Projekt-Root bleibt sauber):

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Ergebnis: `_build\Cipher-Setup-0.1.0.exe` (Installer) und `_build\dist\Cipher\` (exe-Ordner).
`-ExecutionPolicy Bypass` umgeht die Windows-Skriptsperre.

**Oder manuell:**

```powershell
.venv\Scripts\pyinstaller.exe cipher.spec --distpath _build\dist --workpath _build\build
```

Ergebnis: `_build\dist\Cipher\Cipher.exe` + alle DLLs/Ressourcen (inkl. Chromium),
**gross (~250–400 MB)** — normal (QtWebEngine = Chromium).

**Testen vor dem Installer:** `_build\dist\Cipher\Cipher.exe` doppelklicken.
- Startet das Fenster + die Startseite (app://newtab) lädt? → gut.
- **Startseite bleibt leer / Web-View startet nicht?** Dann fehlen QtWebEngine-Ressourcen:

  ```powershell
  .venv\Scripts\pyinstaller.exe --collect-all PyQt6 cipher.spec --distpath _build\dist --workpath _build\build
  ```

  (sammelt alle PyQt6-Daten zwangsweise ein). Falls weiter Probleme: melde dich, das ist
  der typische QtWebEngine-Stolperstein und meist mit 1–2 Anpassungen gelöst.

Nutzerdaten landen beim installierten Build in `%LOCALAPPDATA%\Cipher\` (profile-data,
logs, themes) — **nicht** im Installationsordner (der ist read-only).

## 2. Installer bauen (Inno Setup)

Macht der Schnellweg oben schon mit. Manuell:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Ergebnis: `_build\Cipher-Setup-0.1.0.exe` — das ist die Datei zum Verteilen.

Version in `installer.iss` (`MyAppVersion`) pro Release hochzählen.

**Aufräumen:** alles Gebaute liegt in `_build\` — zum Putzen einfach den Ordner löschen
(`Remove-Item -Recurse -Force _build`).

## 3. Vor öffentlichem Release beachten

- **Quellcode veröffentlichen** (z. B. GitHub): GPL v3 verlangt, dass jeder Nutzer der
  Binaries den Quellcode bekommt.
- **`LICENSE`**: den vollständigen GPL-v3-Text anhängen (siehe Hinweis in der Datei).
- **SmartScreen-Warnung:** ohne Code-Signing-Zertifikat zeigt Windows beim ersten Start
  „Unbekannter Herausgeber". Für privat/Freunde ok (auf „Trotzdem ausführen" klicken);
  ein Zertifikat kostet Geld.
- **Premium/Backend** (Phase 2): die kostenpflichtigen Features laufen später gegen einen
  eigenen Server — der Client hier bleibt gratis + open-source.

## 4. Auto-Update einrichten & neue Versionen veröffentlichen

Cipher prüft beim Start (1×/Tag, im Hintergrund) GitHub Releases und bietet ein Update an.

**Einmalig aktivieren:**
1. Projekt auf **GitHub** veröffentlichen (öffentliches Repo, GPL-Pflicht).
2. In `browser/updater.py` `GITHUB_REPO = "<user>/<repo>"` setzen (z. B. `"damien/cipher"`).
   Leer = Update-Check aus.

**Pro Release:**
1. Version in `browser/version.py` (`__version__`) hochzählen — z. B. `0.2.0`.
2. App bündeln + Installer bauen (Schritte 1–2 oben). Version in `installer.iss`
   (`MyAppVersion`) gleich mitziehen.
3. Auf GitHub ein **Release** anlegen mit Tag **`v0.2.0`** (das `v` ist ok) und das
   `Cipher-Setup-0.2.0.exe` als **Asset** anhängen (Dateiname muss `setup` + `.exe`
   enthalten — der Updater sucht danach).

Installierte Clients sehen das Update beim nächsten Start, laden das Setup und starten es;
der Installer schliesst Cipher, ersetzt die Dateien (gleiche AppId) und startet neu.
