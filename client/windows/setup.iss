; Makia Windows per-user, one-file setup. The panel remains the only login/provision owner.
#define MyVersion "1.6.5.1"
#define MyAppName "Makia Windows"
#define Payload "..\..\package"

[Setup]
AppId=Makia.Windows.FullDevice
AppName={#MyAppName}
AppVersion={#MyVersion}
AppPublisher=Makia
AppPublisherURL=https://p.mahinet.shop/
AppSupportURL=https://p.mahinet.shop/client/
DefaultDirName={localappdata}\Makia\Connector\bin
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\..\installer
OutputBaseFilename=Makia-Windows-Setup-{#MyVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\MakiaWindows.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
ChangesAssociations=yes
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a Makia Windows desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#Payload}\MakiaWindows.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\MakiaClientConnector.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\sing-box.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\wstunnel.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\INSTALL.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#Payload}\BUILD-INFO.txt"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; Explicitly per-user. No HKLM hooks, global browser proxy or admin credentials.
Root: HKCU; Subkey: "Software\Classes\makia"; ValueType: string; ValueName: ""; ValueData: "URL:Makia Client Connector"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\makia"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\makia\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\MakiaClientConnector.exe"",0"
Root: HKCU; Subkey: "Software\Classes\makia\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\MakiaClientConnector.exe"" ""%1"""

[Icons]
Name: "{autoprograms}\Makia Windows"; Filename: "{app}\MakiaWindows.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Makia Windows"; Filename: "{app}\MakiaWindows.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MakiaWindows.exe"; Description: "Open Makia Windows"; Flags: nowait postinstall skipifsilent

[Code]
// Do not replace or uninstall a full-device runtime while its tunnel is
// recorded as active. User must disconnect from the app first.
function TunnelStateExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Makia\Connector\state.json'));
end;

function InitializeSetup(): Boolean;
begin
  Result := not TunnelStateExists();
  if not Result then
    MsgBox('Please disconnect the active Makia tunnel before updating. Open Makia Windows and select Disconnect.', mbError, MB_OK);
end;

function InitializeUninstall(): Boolean;
begin
  Result := not TunnelStateExists();
  if not Result then
    MsgBox('Please disconnect Makia before uninstalling, to avoid leaving a Windows tunnel without its connector.', mbError, MB_OK);
end;
