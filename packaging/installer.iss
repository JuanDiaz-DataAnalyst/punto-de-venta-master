; Instalador de Punto de Venta MASTER - Inno Setup 6 (gratuito): https://jrsoftware.org/isinfo.php
#define AppName "Punto de Venta MASTER"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "PuntoDeVentaMASTER.exe"

[Setup]
; Todas las rutas relativas parten de la raíz del repositorio
SourceDir=..
AppId={{7C1B7E2A-5D3F-4B7A-9E61-2F0A6C3D8B11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Juan Diaz Vega
AppPublisherURL=https://github.com/JuanDiaz-DataAnalyst/punto-de-venta-master
DefaultDirName={autopf}\PuntoDeVentaMASTER
DefaultGroupName={#AppName}
OutputDir=instalador
OutputBaseFilename=Instalar_PuntoDeVentaMASTER_{#AppVersion}
SetupIconFile=packaging\icono.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\PuntoDeVentaMASTER\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{#AppName} (modo navegador)"; Filename: "{app}\{#AppExe}"; Parameters: "--browser"; Comment: "Usar si la ventana propia no abre (sin WebView2)"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

; Nota: los datos (base de datos, respaldos) viven en %LOCALAPPDATA%\PuntoDeVentaMASTER
; y NO se borran al desinstalar, para no perder informacion del negocio.
