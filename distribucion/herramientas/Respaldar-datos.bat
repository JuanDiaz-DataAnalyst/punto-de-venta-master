@echo off
setlocal
title Respaldar datos - Punto de Venta MASTER
rem Copia TODA la carpeta de datos (base de datos, respaldos automaticos, exportaciones y registros).
rem Uso: Respaldar-datos.bat [carpeta_destino]   (por defecto, una carpeta nueva en el Escritorio)
if defined POS_DATA_DIR set "DATOS=%POS_DATA_DIR%"
if not defined POS_DATA_DIR set "DATOS=%LOCALAPPDATA%\PuntoDeVentaMASTER"
if not exist "%DATOS%\pos.db" goto :sindatos

tasklist /FI "IMAGENAME eq PuntoDeVentaMASTER.exe" 2>nul | find /I "PuntoDeVentaMASTER.exe" >nul
if not errorlevel 1 goto :abierto

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "SELLO=%%i"
set "DEST=%USERPROFILE%\Desktop\Respaldo_PuntoDeVenta_%SELLO%"
if not "%~1"=="" set "DEST=%~1\Respaldo_PuntoDeVenta_%SELLO%"
echo Copiando %DATOS%
echo       a %DEST%
robocopy "%DATOS%" "%DEST%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :fallo
echo.
echo [OK] Respaldo creado en: %DEST%
echo Para restaurarlo en otra PC: cierra el sistema y copia el contenido de esa carpeta dentro de
echo %%LOCALAPPDATA%%\PuntoDeVentaMASTER  ^(reemplazando los archivos^).
echo.
pause
exit /b 0

:sindatos
echo No se encontro la base de datos en %DATOS%
pause
exit /b 1

:abierto
echo El sistema esta abierto. Cierralo ^(cierra su ventana^) y vuelve a ejecutar este archivo
echo para que la copia quede completa.
pause
exit /b 1

:fallo
echo [ERROR] No se pudo completar la copia.
pause
exit /b 1
