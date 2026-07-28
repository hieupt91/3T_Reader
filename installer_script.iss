; ================================================================
; Kịch bản tạo bộ cài đặt chuyên nghiệp cho 3T Reader
; ================================================================
#define MyAppName      "3T Reader"
#define MyAppVersion   "1.0.26"
#define MyAppPublisher "3T Company"
#define MyAppExeName   "3T_Reader.exe"

[Setup]
; Stable AppId keeps upgrades aligned across installer versions.
AppId={{D37F8E9A-24C6-4B9A-B1C2-3E4F5D6A7B8C}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://3tcomputer.com
AppSupportURL=https://3tcomputer.com
AppUpdatesURL=https://3tcomputer.com

; Thư mục cài mặc định: C:\Program Files\3T Reader
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UsePreviousAppDir=yes
UsePreviousGroup=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\3T_Reader_SingleInstance_v1
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=3T Reader Windows Installer
VersionInfoProductName={#MyAppName}
SetupLogging=yes
SignedUninstaller=no
; Configure this in Inno Setup IDE/ISCC environment when a certificate is installed:
;   3t_signtool=signtool sign /fd sha256 /td sha256 /tr http://timestamp.digicert.com /a $f
; Or sign output after build with:
;   python scripts\sign_windows.py --file build\installer\Setup_3T_Reader_v{#MyAppVersion}.exe --cert-subject "3T Company"
; SignTool=3t_signtool

; Output
OutputDir=build\installer
OutputBaseFilename=Setup_3T_Reader_v{#MyAppVersion}

; Nén tốt nhất
Compression=lzma2/fast
SolidCompression=no

; Giao diện
WizardStyle=modern
SetupIconFile=assets\app.ico

; Yêu cầu Admin
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Đăng ký file association .pdf để hiện icon đỏ
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no

[Registry]
; Chiếm quyền mở .pdf mặc định — chỉ khi người dùng chọn (ARCH-10)
Root: HKCR; Subkey: ".pdf"; ValueType: string; ValueName: ""; ValueData: "3TReader.PDF"; Flags: uninsdeletevalue; Tasks: pdfassoc
Root: HKCR; Subkey: ".pdf\OpenWithProgids"; ValueType: string; ValueName: "3TReader.PDF"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCR; Subkey: "3TReader.PDF"; ValueType: string; ValueName: ""; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKCR; Subkey: "3TReader.PDF\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\assets\pdf_icon_3t.ico"
Root: HKCR; Subkey: "3TReader.PDF\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\assets\pdf_icon_3t.ico"
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletevalue
; Cho phép nâng cấp không cần gỡ bản cũ

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "pdfassoc"; Description: "Đặt 3T Reader làm ứng dụng mở file PDF mặc định"; GroupDescription: "Liên kết tệp:"

[Files]
; Toàn bộ thư mục build onedir của PyInstaller
Source: "dist\3T_Reader_Secure\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; OCR runtime is packaged by PyInstaller into _internal\Tesseract-OCR so
; installer and portable builds use the same bundled files.

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; \
  Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\{#MyAppExeName}"

; Desktop (tuỳ chọn — người dùng tích vào)
Name: "{autodesktop}\{#MyAppName}"; \
  Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Run]
; Chạy app sau khi cài xong (tuỳ chọn)
Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden

[UninstallDelete]
; Xoá sạch thư mục khi gỡ cài đặt
Type: filesandordirs; Name: "{app}"

[Code]
procedure RefreshShellIcons(wEventId, uFlags, dwItem1, dwItem2: Longint);
external 'SHChangeNotify@shell32.dll stdcall';
const
  SHCNE_ASSOCCHANGED = $08000000;
  SHCNF_IDLIST = $0000;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // Báo Explorer nạp lại icon ngay, không cần đăng xuất/khởi động lại
  if CurStep = ssPostInstall then
    RefreshShellIcons(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RefreshShellIcons(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0);
end;
