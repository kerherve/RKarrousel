; Installateur Windows de RKarrousel (Inno Setup 6).
; Compilation : ISCC.exe /DAppVersion=0.7.0 installer\RKarrousel.iss   (l'exe doit être dans ..\dist\RKarrousel.exe)
; Installation par utilisateur (sans droits administrateur) : la config est stockée à côté de l'exécutable.

#define MyAppName "RKarrousel"
#define MyAppExe "RKarrousel.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B7F2C1D4-6E3A-4C58-9F21-5A8D0E7B3C64}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher=Riwal Kerherve
AppPublisherURL=https://github.com/kerherve/RKarrousel
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename={#MyAppName}-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExe}
VersionInfoVersion={#AppVersion}.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.DeleteSettings=Also delete your RKarrousel settings?
french.DeleteSettings=Supprimer aussi vos réglages RKarrousel ?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "default_config.json"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\gdrive_token.json"
Type: files; Name: "{app}\image_splitter.log"
Type: files; Name: "{app}\image_splitter.log.1"

[Code]
const
  ConfigName = '.image_splitter_config.json';

function Hex4(C: Integer): string;
var
  Digits: string;
begin
  Digits := '0123456789abcdef';
  Result := Digits[(C div 4096) mod 16 + 1] + Digits[(C div 256) mod 16 + 1] +
            Digits[(C div 16) mod 16 + 1] + Digits[C mod 16 + 1];
end;

// Valeur sûre pour du JSON : '\' -> '/', guillemets échappés, caractères non ASCII en \uXXXX.
function JsonEscape(const S: string): string;
var
  I, C: Integer;
begin
  Result := '';
  for I := 1 to Length(S) do
  begin
    C := Ord(S[I]);
    if S[I] = '\' then
      Result := Result + '/'
    else if S[I] = '"' then
      Result := Result + '\"'
    else if C > 126 then
      Result := Result + '\u' + Hex4(C)
    else
      Result := Result + S[I];
  end;
end;

// Crée les réglages par défaut au premier install ; ne touche jamais à une config existante (mise à jour).
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile, Template, Lang: string;
  Raw: AnsiString;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigFile := ExpandConstant('{app}\') + ConfigName;
    if not FileExists(ConfigFile) then
    begin
      if ActiveLanguage = 'french' then Lang := 'fr' else Lang := 'en';
      if LoadStringFromFile(ExpandConstant('{tmp}\default_config.json'), Raw) then
      begin
        Template := String(Raw);
        StringChangeEx(Template, '@LANG@', Lang, True);
        StringChangeEx(Template, '@DOCS@', JsonEscape(ExpandConstant('{userdocs}')), True);
        SaveStringToFile(ConfigFile, Template, False);
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigFile: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ConfigFile := ExpandConstant('{app}\') + ConfigName;
    if FileExists(ConfigFile) then
      if MsgBox(CustomMessage('DeleteSettings'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DeleteFile(ConfigFile);
  end;
end;
