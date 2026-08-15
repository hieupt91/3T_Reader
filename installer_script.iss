; ================================================================
; Kịch bản tạo bộ cài đặt chuyên nghiệp cho 3T Reader
; ================================================================
#define MyAppName      "3T Reader"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.34"
#endif
#ifndef BuildSource
  #define BuildSource "dist\\3T_Reader_Secure"
#endif
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

; Giao diện chuyên nghiệp - ảnh sinh từ scripts/build_installer_assets.py
; (dùng brand_appicon_512.png/icon_128.png có sẵn, giữ đúng màu thương hiệu
; cam #FF7700->#FF4400 đã dùng xuyên suốt UI trong app).
WizardStyle=modern
WizardImageFile=assets\installer\wizard_large.bmp
WizardSmallImageFile=assets\installer\wizard_small.bmp
WizardImageStretch=no
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
; DefaultIcon PHẢI trỏ vào {app}\_internal\assets\... (không phải
; {app}\assets\...) - PyInstaller onedir (bản build hiện tại) đặt mọi thứ
; ngoài chính file .exe vào thư mục con _internal\, kể cả assets\. Đường dẫn
; cũ thiếu _internal\ trỏ tới file không tồn tại -> Explorer hiện icon PDF
; mặc định của Windows thay vì icon 3T Reader, xác nhận thật 14/08/2026 bằng
; cách đọc registry trên máy đã cài qua đúng installer này.
Root: HKCR; Subkey: ".pdf"; ValueType: string; ValueName: ""; ValueData: "3TReader.PDF"; Flags: uninsdeletevalue; Tasks: pdfassoc
Root: HKCR; Subkey: ".pdf\OpenWithProgids"; ValueType: string; ValueName: "3TReader.PDF"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCR; Subkey: "3TReader.PDF"; ValueType: string; ValueName: ""; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKCR; Subkey: "3TReader.PDF\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\_internal\assets\pdf_icon_3t.ico"
Root: HKCR; Subkey: "3TReader.PDF\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCR; Subkey: "Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Applications\{#MyAppExeName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\_internal\assets\pdf_icon_3t.ico"
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
Source: "{#BuildSource}\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; OCR runtime is packaged by PyInstaller into _internal\Tesseract-OCR so
; installer and portable builds use the same bundled files.

; Ảnh giới thiệu tính năng hiện trong lúc cài (trang Installing) - dontcopy
; nghĩa là chỉ giải nén tạm vào {tmp} lúc setup chạy (qua ExtractTemporaryFile
; trong [Code]), KHÔNG cài vào {app} - sinh bởi scripts/build_installer_assets.py.
Source: "assets\installer\feature_slide_1.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "assets\installer\feature_slide_2.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "assets\installer\feature_slide_3.bmp"; DestDir: "{tmp}"; Flags: dontcopy
Source: "assets\installer\feature_slide_4.bmp"; DestDir: "{tmp}"; Flags: dontcopy

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
; Mở firewall cho tính năng "Nhận từ ĐT" (P2P WebRTC ScanDoc) - installer đã
; chạy quyền admin sẵn (PrivilegesRequired=admin) nên làm được ngay lúc cài,
; người dùng không cần tự bấm Allow / đổi Network profile sang Private sau
; này (phát hiện thực nghiệm: mạng WiFi "Public" mặc định của Windows chặn
; hết inbound, khiến kết nối trực tiếp tới ScanDoc luôn timeout).
Filename: "{sys}\netsh.exe"; \
  Parameters: "advfirewall firewall add rule name=""3T Reader (ScanDoc P2P)"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes profile=any"; \
  Flags: runhidden; \
  StatusMsg: "Đang cấu hình tường lửa cho tính năng nhận tài liệu..."
; Chạy app sau khi cài xong (tuỳ chọn)
Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent
Filename: "{sys}\ie4uinit.exe"; Parameters: "-ClearIconCache"; Flags: runhidden
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden

[UninstallRun]
Filename: "{sys}\netsh.exe"; \
  Parameters: "advfirewall firewall delete rule name=""3T Reader (ScanDoc P2P)"" program=""{app}\{#MyAppExeName}"""; \
  Flags: runhidden; RunOnceId: "RemoveScanDocFirewallRule"

[UninstallDelete]
; Xoá sạch thư mục khi gỡ cài đặt
Type: filesandordirs; Name: "{app}"

[Code]
procedure RefreshShellIcons(wEventId, uFlags, dwItem1, dwItem2: Longint);
external 'SHChangeNotify@shell32.dll stdcall';
function GetTickCount: LongWord;
external 'GetTickCount@kernel32.dll stdcall';
const
  SHCNE_ASSOCCHANGED = $08000000;
  SHCNF_IDLIST = $0000;
  FeatureSlideCount = 4;

var
  FeatureImage: TBitmapImage;
  FeatureIndex: Integer;
  FeatureLastSwitchTick: DWORD;

// Trang "Installing" chỉ có progress bar trơn, khá tẻ nhạt lúc chờ - hiện
// luân phiên 4 ảnh giới thiệu tính năng (assets/installer/feature_slide_*.bmp,
// sinh bởi scripts/build_installer_assets.py) để trông chuyên nghiệp hơn,
// giống các bộ cài lớn (Steam, Adobe...) hay làm. TTimer không có trong bản
// Pascal Script này (ISCC 6.7.3 báo "Unknown type 'TTimer'") - dùng
// CurInstallProgressChanged (Inno tự gọi liên tục lúc cài) + GetTickCount
// để đổi ảnh mỗi ~3s thay vì cần timer thật.
procedure LoadFeatureSlide(Index: Integer);
var
  FileName: String;
begin
  FileName := ExpandConstant('{tmp}\feature_slide_' + IntToStr(Index) + '.bmp');
  if FileExists(FileName) then
    FeatureImage.Bitmap.LoadFromFile(FileName);
end;

procedure InitializeWizard();
var
  I: Integer;
begin
  for I := 1 to FeatureSlideCount do
    ExtractTemporaryFile('feature_slide_' + IntToStr(I) + '.bmp');

  FeatureImage := TBitmapImage.Create(WizardForm);
  FeatureImage.Parent := WizardForm.InstallingPage;
  FeatureImage.Left := WizardForm.ProgressGauge.Left;
  FeatureImage.Top := WizardForm.ProgressGauge.Top + WizardForm.ProgressGauge.Height + 24;
  FeatureImage.Width := WizardForm.ProgressGauge.Width;
  FeatureImage.Height := 138;
  FeatureImage.Stretch := True;
  FeatureImage.Center := False;

  FeatureIndex := 1;
  LoadFeatureSlide(FeatureIndex);
  FeatureLastSwitchTick := GetTickCount;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  if GetTickCount - FeatureLastSwitchTick >= 3000 then
  begin
    FeatureIndex := FeatureIndex + 1;
    if FeatureIndex > FeatureSlideCount then
      FeatureIndex := 1;
    LoadFeatureSlide(FeatureIndex);
    FeatureLastSwitchTick := GetTickCount;
  end;
end;

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
