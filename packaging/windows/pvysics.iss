; Inno Setup script: iscc /DVersion=0.1.0 packaging\windows\pvysics.iss
[Setup]
AppName=PV Digital Twin
AppVersion={#Version}
DefaultDirName={autopf}\pvysics
DefaultGroupName=PV Digital Twin
OutputDir=..\..\dist
OutputBaseFilename=pvysics-{#Version}-windows-setup
SetupIconFile=..\..\build\icons\icon.ico
Compression=lzma2
SolidCompression=yes

[Files]
Source: "..\..\dist\pvysics\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PV Digital Twin"; Filename: "{app}\pvysics.exe"
Name: "{autodesktop}\PV Digital Twin"; Filename: "{app}\pvysics.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop icon"
