@echo off
setlocal
title Verificar equipo - Punto de Venta MASTER
echo ==================================================
echo    Verificacion del equipo para Punto de Venta MASTER
echo ==================================================
echo.

rem --- Windows y arquitectura ---
for /f "tokens=*" %%v in ('ver') do set "WINVER=%%v"
echo Windows: %WINVER%
set "ARQ=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "ARQ=%PROCESSOR_ARCHITEW6432%"
if /i "%ARQ%"=="AMD64" echo [OK]    Windows de 64 bits
if /i not "%ARQ%"=="AMD64" echo [AVISO] Se necesita Windows de 64 bits. Arquitectura detectada: %ARQ%

rem --- WebView2 (la ventana propia del sistema) ---
set "WV2="
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2=1"
reg query "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2=1"
reg query "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1 && set "WV2=1"
if defined WV2 echo [OK]    Microsoft Edge WebView2 instalado
if not defined WV2 echo [AVISO] No se encontro Microsoft Edge WebView2 Runtime.
if not defined WV2 echo         El sistema funcionara abriendose en el navegador ^(acceso "modo navegador"^).
if not defined WV2 echo         Para la ventana propia instala WebView2: https://developer.microsoft.com/microsoft-edge/webview2/

rem --- Puerto del sistema ---
netstat -ano | findstr /R /C:":8765 .*LISTENING" >nul 2>&1
set "EN_USO=%errorlevel%"
if "%EN_USO%"=="0" echo [INFO]  El puerto 8765 esta en uso ^(normal si el sistema esta abierto; si no, el sistema elige otro solo^).
if not "%EN_USO%"=="0" echo [OK]    Puerto 8765 libre

rem --- Instalacion y datos ---
set "INSTALADO="
if exist "%ProgramFiles%\PuntoDeVentaMASTER\PuntoDeVentaMASTER.exe" set "INSTALADO=%ProgramFiles%\PuntoDeVentaMASTER"
if exist "%LOCALAPPDATA%\Programs\PuntoDeVentaMASTER\PuntoDeVentaMASTER.exe" set "INSTALADO=%LOCALAPPDATA%\Programs\PuntoDeVentaMASTER"
if defined INSTALADO echo [OK]    Instalado en %INSTALADO%
if not defined INSTALADO echo [INFO]  El sistema aun no esta instalado en este equipo.
if defined POS_DATA_DIR set "DATOS=%POS_DATA_DIR%"
if not defined POS_DATA_DIR set "DATOS=%LOCALAPPDATA%\PuntoDeVentaMASTER"
if exist "%DATOS%\pos.db" echo [OK]    Base de datos encontrada en %DATOS%
if not exist "%DATOS%\pos.db" echo [INFO]  Aun no hay base de datos ^(se crea al abrir el sistema por primera vez^).

rem --- Impresora predeterminada ---
set "IMP="
for /f "delims=" %%p in ('powershell -NoProfile -Command "(Get-CimInstance Win32_Printer ^| Where-Object Default).Name" 2^>nul') do set "IMP=%%p"
if defined IMP echo [OK]    Impresora predeterminada: %IMP%
if not defined IMP echo [AVISO] No se detecto impresora predeterminada ^(necesaria para imprimir tickets^).

echo.
echo Listo. Los avisos no impiden instalar, pero conviene resolverlos.
echo.
pause
