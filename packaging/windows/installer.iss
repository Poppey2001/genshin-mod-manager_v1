#define MyAppName "Genshin Mod Manager"
#define MyAppPublisher "Poppey2001"
#define MyAppExeName "GenshinModManager.exe"
#define MyAgentExeName "GMMUpdateAgent.exe"

#define PythonVersion "3.12.10"
#define PythonInstallerName "python-3.12.10-amd64.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{B74B4D5B-2A89-4DA4-8C50-0C7EEA5EAA57}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/Poppey2001/genshin-mod-manager_v1
AppSupportURL=https://github.com/Poppey2001/genshin-mod-manager_v1/issues
AppUpdatesURL=https://github.com/Poppey2001/genshin-mod-manager_v1/releases
DefaultDirName={localappdata}\Programs\Genshin Mod Manager
DefaultGroupName=Genshin Mod Manager
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\release
OutputBaseFilename=Genshin-Mod-Manager-Setup-{#MyAppVersion}-x86_64
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
UsePreviousTasks=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[CustomMessages]
english.PythonTask=Install Python 3.12 for the current user (automatically skipped when Python 3.12 or newer is already installed)
german.PythonTask=Python 3.12 für den aktuellen Benutzer installieren (wird automatisch übersprungen, wenn Python 3.12 oder neuer bereits installiert ist)

english.PythonStatus=Installing Python 3.12 for the current user...
german.PythonStatus=Python 3.12 wird für den aktuellen Benutzer installiert...

english.PythonDetected=Python 3.12 or newer is already installed. The bundled Python installation will be skipped.
german.PythonDetected=Python 3.12 oder neuer ist bereits installiert. Die mitgelieferte Python-Installation wird übersprungen.

english.AgentAutostartTask=Start GMM Update Agent automatically with Windows
german.AgentAutostartTask=GMM Update Agent automatisch mit Windows starten

english.AgentAutoCheckTask=Automatically check for GMM updates in the background
german.AgentAutoCheckTask=Automatisch im Hintergrund nach GMM-Updates suchen

english.AgentLaunchTask=Start GMM Update Agent
german.AgentLaunchTask=GMM Update Agent starten

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "agentautostart"; Description: "{cm:AgentAutostartTask}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: checkedonce
Name: "agentautocheck"; Description: "{cm:AgentAutoCheckTask}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: checkedonce

; Python is optional. If Python 3.12+ is already present, the task is
; not offered at all. Otherwise it is selected on the first install.
; UsePreviousTasks=yes preserves the user's choice for later upgrades.
Name: "python"; Description: "{cm:PythonTask}"; Flags: checkedonce; Check: not IsPython312OrNewerInstalled

[Files]
Source: "..\..\dist\GenshinModManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\GMMUpdateAgent.exe"; DestDir: "{app}"; DestName: "{#MyAgentExeName}"; Flags: ignoreversion

; The official CPython installer is downloaded and signature-checked by
; scripts\build_windows_installer.ps1 before Inno Setup is compiled.
Source: "..\..\packaging\windows\redist\{#PythonInstallerName}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Tasks: python; Check: not IsPython312OrNewerInstalled

[Icons]
Name: "{group}\Genshin Mod Manager"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Genshin Mod Manager"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Poppey2001\GenshinModManager"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Poppey2001\GenshinModManager"; ValueType: string; ValueName: "InstalledVersion"; ValueData: "{#MyAppVersion}"

[Run]
; Python is deliberately installed per-user and silently. The Mod Manager
; itself is a frozen PyInstaller build and does not depend on this external
; interpreter; Python is an optional convenience/runtime for scripts.
Filename: "{tmp}\{#PythonInstallerName}"; Parameters: "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_launcher=1 InstallLauncherAllUsers=0 Shortcuts=0"; StatusMsg: "{cm:PythonStatus}"; Flags: waituntilterminated runhidden; Tasks: python; Check: not IsPython312OrNewerInstalled

; Always refresh Update Agent installation paths/version without overwriting the
; user's existing autostart/automatic-check decisions on upgrades.
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --gmm-path ""{app}\{#MyAppExeName}"" --agent-path ""{app}\{#MyAgentExeName}"" --installed-version ""{#MyAppVersion}"""; Flags: waituntilterminated runhidden runasoriginaluser

; When the Update Agent is introduced for the first time, apply the choices
; made on the Tasks page. Later upgrades preserve the Agent configuration.
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --autostart yes"; Flags: waituntilterminated runhidden runasoriginaluser; Tasks: agentautostart; Check: IsFreshAgentInstall
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --autostart no"; Flags: waituntilterminated runhidden runasoriginaluser; Check: FreshInstallWithoutAgentAutostart
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --auto-check yes --interval 20"; Flags: waituntilterminated runhidden runasoriginaluser; Tasks: agentautocheck; Check: IsFreshAgentInstall
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --auto-check no --interval 20"; Flags: waituntilterminated runhidden runasoriginaluser; Check: FreshInstallWithoutAgentAutoCheck

; Normal interactive install: offer start on Finish page.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Genshin Mod Manager}"; Flags: nowait postinstall runasoriginaluser skipifsilent
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--background"; Description: "{cm:AgentLaunchTask}"; Flags: nowait postinstall runasoriginaluser skipifsilent; Check: IsAgentAutostartEnabled

; Silent auto-update: restart Agent and GMM automatically after Setup completed.
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--background"; Flags: nowait runasoriginaluser skipifnotsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser skipifnotsilent

[UninstallRun]
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--write-config --autostart no"; Flags: waituntilterminated runhidden; RunOnceId: "DisableAgentAutostart"
Filename: "{app}\{#MyAgentExeName}"; Parameters: "--shutdown"; Flags: waituntilterminated runhidden; RunOnceId: "ShutdownAgent"
Filename: "{cmd}"; Parameters: "/C timeout /T 1 /NOBREAK >NUL & taskkill /IM {#MyAgentExeName} /F >NUL 2>&1"; Flags: waituntilterminated runhidden; RunOnceId: "ForceStopAgent"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]

var
  HadExistingAgentConfig: Boolean;

function InitializeSetup: Boolean;
begin
  HadExistingAgentConfig := FileExists(
    ExpandConstant(
      '{localappdata}\Genshin Mod Manager\UpdateAgent\update-agent.json'
    )
  );
  Result := True;
end;

function IsFreshAgentInstall: Boolean;
begin
  Result := not HadExistingAgentConfig;
end;

function FreshInstallWithoutAgentAutostart: Boolean;
begin
  Result :=
    (not HadExistingAgentConfig)
    and
    (not WizardIsTaskSelected('agentautostart'));
end;

function FreshInstallWithoutAgentAutoCheck: Boolean;
begin
  Result :=
    (not HadExistingAgentConfig)
    and
    (not WizardIsTaskSelected('agentautocheck'));
end;

function IsAgentAutostartEnabled: Boolean;
var
  CommandLine: String;
begin
  Result := RegQueryStringValue(
    HKCU,
    'Software\Microsoft\Windows\CurrentVersion\Run',
    'GMMUpdateAgent',
    CommandLine
  );
end;


function ParsePythonVersion(
  VersionName: String;
  var Major: Integer;
  var Minor: Integer
): Boolean;
var
  DotPos: Integer;
  Rest: String;
  SecondDotPos: Integer;
  MajorText: String;
  MinorText: String;
begin
  Result := False;
  Major := 0;
  Minor := 0;

  DotPos := Pos('.', VersionName);

  if DotPos <= 1 then
    Exit;

  MajorText := Copy(
    VersionName,
    1,
    DotPos - 1
  );

  Rest := Copy(
    VersionName,
    DotPos + 1,
    Length(VersionName)
  );

  SecondDotPos := Pos('.', Rest);

  if SecondDotPos > 0 then
    MinorText := Copy(
      Rest,
      1,
      SecondDotPos - 1
    )
  else
    MinorText := Rest;

  Major := StrToIntDef(
    MajorText,
    -1
  );

  Minor := StrToIntDef(
    MinorText,
    -1
  );

  Result := (
    (Major >= 0)
    and
    (Minor >= 0)
  );
end;


function PythonVersionIsSupported(
  VersionName: String
): Boolean;
var
  Major: Integer;
  Minor: Integer;
begin
  Result := False;

  if not ParsePythonVersion(
    VersionName,
    Major,
    Minor
  ) then
    Exit;

  Result := (
    (Major > 3)
    or
    (
      (Major = 3)
      and
      (Minor >= 12)
    )
  );
end;


function PythonInstallExists(
  RootKey: Integer;
  VersionName: String
): Boolean;
var
  KeyName: String;
  ExecutablePath: String;
  InstallPath: String;
begin
  Result := False;

  KeyName :=
    'Software\Python\PythonCore\'
    + VersionName
    + '\InstallPath';

  if RegQueryStringValue(
    RootKey,
    KeyName,
    'ExecutablePath',
    ExecutablePath
  ) then
  begin
    if FileExists(
      ExecutablePath
    ) then
    begin
      Result := True;
      Exit;
    end;
  end;

  if RegQueryStringValue(
    RootKey,
    KeyName,
    '',
    InstallPath
  ) then
  begin
    if FileExists(
      AddBackslash(
        InstallPath
      )
      + 'python.exe'
    ) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;


function RegistryContainsSupportedPython(
  RootKey: Integer
): Boolean;
var
  Versions: TArrayOfString;
  Index: Integer;
  VersionName: String;
begin
  Result := False;

  if not RegGetSubkeyNames(
    RootKey,
    'Software\Python\PythonCore',
    Versions
  ) then
    Exit;

  for Index := 0 to GetArrayLength(Versions) - 1 do
  begin
    VersionName := Versions[Index];

    if (
      PythonVersionIsSupported(
        VersionName
      )
      and
      PythonInstallExists(
        RootKey,
        VersionName
      )
    ) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;


function IsPython312OrNewerInstalled: Boolean;
begin
  Result := False;

  if RegistryContainsSupportedPython(
    HKCU
  ) then
  begin
    Result := True;
    Exit;
  end;

  if IsWin64 then
  begin
    if RegistryContainsSupportedPython(
      HKLM64
    ) then
    begin
      Result := True;
      Exit;
    end;

    if RegistryContainsSupportedPython(
      HKLM32
    ) then
    begin
      Result := True;
      Exit;
    end;
  end
  else
  begin
    if RegistryContainsSupportedPython(
      HKLM
    ) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;
