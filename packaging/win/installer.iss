; Inno Setup 脚本：把 onedir 产物打成可在用户电脑上安装的 Setup.exe
; 编译：ISCC.exe packaging\win\installer.iss
#define MyAppName "纳多狐狐的写作台"
#define MyAppVersion "2.9"
#define MyAppPublisher "LeonardoFox346"
#define MyAppExe "NardoFoxWriteDesk.exe"
#define MyAppId "{{6F0B2C1E-7A64-4E2B-9C3D-2A9F5E1B8D44}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NardoFoxWriteDesk
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=NardoFoxWriteDesk-Setup-2.9
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\app.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\EULA.txt

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Languages: chinesesimplified
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks:"; Languages: english

[Files]
Source: "..\..\dist\NardoFoxWriteDesk\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\EULA.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
