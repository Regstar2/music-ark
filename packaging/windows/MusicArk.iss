#ifndef MyAppVersion
  #error MyAppVersion must be supplied with /DMyAppVersion=x.y.z
#endif
#ifndef SourceDir
  #error SourceDir must be supplied with /DSourceDir=...
#endif
#ifndef OutputDir
  #error OutputDir must be supplied with /DOutputDir=...
#endif

#define MyAppName "Music Ark"
#define MyAppPublisher "Music Ark"
#define MyAppExeName "Music Ark.exe"

[Setup]
AppId={{8D5B49CA-C1C4-4BBA-B4F4-0C7E5877C56E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Music Ark
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=MusicArk-Setup-{#MyAppVersion}-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Music Ark Windows installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Music Ark"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Music Ark"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Music Ark}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  { User data lives outside the application directory. The uninstaller intentionally leaves the }
  { MusicArk database/cache/configuration and external programs such as WARP }
  { untouched. External dependency removal requires a separate explicit user }
  { action so an uninstall cannot silently remove software used elsewhere. }
  Result := True;
end;
