; Installer for the BAP Price Robot (Robot de Precios).
; Build dist\RobotDePrecios.exe first, then compile this script with Inno Setup 6.3 or newer
; (build_windows.ps1 does both). The result is dist\RobotDePrecios_Instalador.exe.
;
; What it does (no administrator rights needed):
;   - puts RobotDePrecios.exe in %LOCALAPPDATA%\Robot de Precios (settings, caches and logs are saved there too)
;   - creates Documents\Robot de Precios, where results are saved
;   - adds a desktop shortcut and a Start menu entry
; The uninstaller (Settings > Apps, or the Start menu) closes the app, removes the AppData folder and
; both shortcuts, and asks before deleting the results in Documents.

#define AppName "Robot de Precios"
#define AppVersion "1.0.0"
#define AppPublisher "Banco de Alimentos Panamá"
#define AppFolder "Robot de Precios"
#define AppExe "RobotDePrecios.exe"

[Setup]
AppId={{C05475DE-4DB5-4D22-A2CE-489047E52F91}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\{#AppFolder}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=RobotDePrecios_Instalador
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
; Spanish only, whatever language Windows uses
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
spanish.DeleteResults=¿También desea borrar los resultados guardados en:%n%1%n%nSi elige No, se conservan.

[Dirs]
Name: "{userdocs}\{#AppFolder}"; Flags: uninsneveruninstall

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; the English uninstall shortcut made by the first test version of this installer
Type: files; Name: "{userprograms}\Uninstall {#AppName}.lnk"

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userprograms}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; everything the app saved beside itself: ui_settings.json, caché\, logs
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Results: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    { Close the app (and a search still running in the background) so its files can be removed. }
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    Results := ExpandConstant('{userdocs}\{#AppFolder}');
    if DirExists(Results) and not UninstallSilent then
      if MsgBox(FmtMessage(CustomMessage('DeleteResults'), [Results]), mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Results, True, True, True);
  end;
end;
