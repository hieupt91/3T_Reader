; Inno Setup script — 3T Reader Windows Installer
; Yêu cầu: PyInstaller đã build xong tại dist\win\3T_Reader\

#define AppName "3T Reader"
#define AppVersion "1.0.2"
#define AppPublisher "3T Company"
#define AppExeName "3T_Reader.exe"

[Setup]
AppId={{A3B2C1D0-1234-5678-ABCD-3TREADER0001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://3tcompany.vn
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Không yêu cầu admin — cài per-user
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist\win
OutputBaseFilename=3T_Reader_Setup_{#AppVersion}
SetupIconFile=..\..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Hiển thị tiếng Việt
ShowLanguageDialog=no
SignedUninstaller=yes
; Configure 3t_signtool in Inno Setup when a code signing certificate is available.
; SignTool=3t_signtool

[Languages]
Name: "vietnamese"; MessagesFile: "compiler:Languages\Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng trên Desktop"; GroupDescription: "Biểu tượng:"; Flags: unchecked

[Files]
Source: "..\..\dist\win\3T_Reader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Khởi động {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\3T Reader"
