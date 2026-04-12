; Dioptas Inno Setup Script
; This script is used by the release workflow to create a Windows installer.
; The {#DioptasVersion} and {#DioptasFolder} defines are passed via the
; command line: iscc /DdioptasVersion=X.Y.Z /DDioptasFolder=... dioptas.iss

#ifndef DioptasVersion
  #define DioptasVersion "0.0.0"
#endif

#ifndef DioptasFolder
  #define DioptasFolder "..\..\dist\Dioptas"
#endif

[Setup]
AppName=Dioptas
AppVersion={#DioptasVersion}
AppPublisher=Clemens Prescher
AppPublisherURL=https://github.com/CPrescher/Dioptas
DefaultDirName={localappdata}\Dioptas
DefaultGroupName=Dioptas
UninstallDisplayIcon={app}\Dioptas.exe
OutputBaseFilename=Dioptas_{#DioptasVersion}_Setup
OutputDir=..\..\dist
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\..\dioptas\resources\icons\icon.ico
LicenseFile=..\..\LICENSE.txt
WizardStyle=modern

[Files]
Source: "{#DioptasFolder}\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\Dioptas"; Filename: "{app}\Dioptas.exe"; IconFilename: "{app}\Dioptas.exe"
Name: "{group}\Uninstall Dioptas"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Dioptas"; Filename: "{app}\Dioptas.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\Dioptas.exe"; Description: "Launch Dioptas"; Flags: postinstall nowait skipifsilent
