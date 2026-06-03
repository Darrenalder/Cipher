# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Build für Cipher (onedir, GUI, QtWebEngine).

    pip install pyinstaller pillow
    pyinstaller cipher.spec

Ergebnis: dist\\Cipher\\Cipher.exe (+ Begleit-Dateien). WICHTIG: onedir, NICHT onefile —
QtWebEngine braucht QtWebEngineProcess.exe + Ressourcen als Dateien daneben (onefile
entpackt in temp und die Web-View startet dann oft nicht). Die QtWebEngine-Binaries/
-Ressourcen sammeln PyInstallers PyQt6-Hooks automatisch ein.
"""
import os

_icon = next((p for p in ("assets/icon.ico", "assets/icon.png") if os.path.exists(p)), None)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("themes", "themes"),   # mitgelieferte Theme-Vorlagen (werden beim 1. Start nach AppData kopiert)
        ("assets", "assets"),   # Icon
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Cipher",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # GUI-App, kein Konsolenfenster
    icon=_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Cipher",
)
