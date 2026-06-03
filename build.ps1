# build.ps1 — Cipher bauen: exe (PyInstaller) + Installer (Inno Setup) → alles nach _build\
#
# Aufruf (im Projektordner):
#   powershell -ExecutionPolicy Bypass -File build.ps1
# (das -ExecutionPolicy Bypass umgeht die Standard-Skriptsperre von Windows)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/2  PyInstaller (exe) ==" -ForegroundColor Cyan
& ".\.venv\Scripts\pyinstaller.exe" cipher.spec --noconfirm `
    --distpath "_build\dist" --workpath "_build\build"

Write-Host "== 2/2  Inno Setup (Installer) ==" -ForegroundColor Cyan
$iscc = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "ISCC.exe nicht gefunden - ist Inno Setup installiert? Installer-Schritt uebersprungen." -ForegroundColor Yellow
    Write-Host "Die exe liegt trotzdem in _build\dist\Cipher\Cipher.exe" -ForegroundColor Yellow
} else {
    & $iscc installer.iss
}

Write-Host "Fertig. Ergebnis in _build\  (Installer: _build\Cipher-Setup-*.exe)" -ForegroundColor Green
