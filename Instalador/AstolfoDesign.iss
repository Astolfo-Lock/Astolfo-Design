#define MyAppName "Astolfo Design"
#define MyAppVersion "1.4.1"
#define MyAppPublisher "Astolfo Design"
#define MyAppExeName "AstolfoDesign.exe"

#ifndef SetupLoaderMode
  #define SetupLoaderMode "yes"
#endif
#ifndef InstallerOutputDir
  #define InstallerOutputDir "Salida"
#endif
#ifndef InstallerFilename
  #define InstallerFilename "Instalador_AstolfoDesign"
#endif

[Setup]
AppId={{2BCA1D23-4FF5-4B1A-A428-276145605631}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Instalador de Astolfo Design
VersionInfoCompany={#MyAppPublisher}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Astolfo Design
DefaultGroupName=Astolfo Design
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir={#InstallerOutputDir}
OutputBaseFilename={#InstallerFilename}
UseSetupLdr={#SetupLoaderMode}
SetupIconFile=instalador.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "App\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "archivo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Astolfo Design"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Astolfo Design"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Registry]
Root: HKA; Subkey: "Software\Classes\.astolfo"; ValueType: string; ValueName: ""; ValueData: "AstolfoDesign.Document"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\AstolfoDesign.Document"; ValueType: string; ValueName: ""; ValueData: "Diseño de Astolfo Design"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\AstolfoDesign.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\archivo.ico"",0"
Root: HKA; Subkey: "Software\Classes\AstolfoDesign.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Astolfo Design"; Flags: nowait postinstall skipifsilent
