; ================================================================
; Kịch bản tạo bộ cài đặt chuyên nghiệp cho 3T Reader
; ================================================================
#define MyAppName      "3T Reader"
#define MyAppVersion   "1.0.2"
#define MyAppPublisher "3T Company"
#define MyAppExeName   "3T_Reader.exe"

[Setup]
AppId={{D37F8E9A-24C6-4B9A-B1C2-3E4F5D6A7B8C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://3tcompany.vn
AppSupportURL=https://3tcompany.vn
AppUpdatesURL=https://3tcompany.vn

; Thư mục cài mặc định: C:\Program Files\3T Reader
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Output
OutputDir=D:\reader_pdf\dist
OutputBaseFilename=Setup_3T_Reader_v{#MyAppVersion}

; Nén tốt nhất
Compression=lzma2/ultra64
SolidCompression=yes

; Giao diện
WizardStyle=modern

; Yêu cầu Admin
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; KHÔNG đăng ký file association .pdf
; (tránh Windows dùng app này làm handler .pdf → gây re-launch khi in)
ChangesAssociations=no

; Cho phép nâng cấp không cần gỡ bản cũ
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Toàn bộ thư mục build onedir của PyInstaller
Source: "dist\3T_Reader\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

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

[UninstallDelete]
; Xoá sạch thư mục khi gỡ cài đặt
Type: filesandordirs; Name: "{app}"
