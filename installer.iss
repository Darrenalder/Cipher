; Inno Setup Script für Cipher — baut aus dem PyInstaller-Output ein setup.exe.
; Voraussetzung: vorher `pyinstaller cipher.spec` (Output in dist\Cipher\).
; Bauen: Inno Setup installieren (https://jrsoftware.org/isdl.php), dann diese .iss
;        in der Inno-IDE öffnen und "Compile" (oder: ISCC.exe installer.iss).

#define MyAppName "Cipher"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Damien"
#define MyAppExeName "Cipher.exe"

[Setup]
; AppId identifiziert die App (für Updates/Deinstallation) — STABIL lassen, nicht ändern.
AppId={{B7E9F3A1-4C2D-4E8A-9F1B-3A6C8D2E5F70}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputBaseFilename=Cipher-Setup-{#MyAppVersion}
; Setup landet im separaten Build-Ordner (sauberer Projekt-Root).
OutputDir=_build
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Ohne Admin installierbar (landet dann im User-Bereich). Nutzerdaten (profile-data, logs)
; liegen ohnehin in %LOCALAPPDATA%\Cipher, nicht im Installationsordner.
PrivilegesRequired=lowest
LicenseFile=LICENSE
; Für saubere In-Place-Updates: laufendes Cipher per Restart-Manager schliessen,
; Dateien ersetzen, danach neu starten (der Auto-Updater lädt+startet dieses Setup).
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "_build\dist\Cipher\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
