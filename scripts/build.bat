@echo off
setlocal
rem Siempre trabajar desde la raiz del repositorio
cd /d "%~dp0.."
title Compilar Punto de Venta MASTER
echo ==================================================
echo    Compilando Punto de Venta MASTER para Windows
echo ==================================================
echo.

rem --- Buscar Python (se recomienda 3.12) ---
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] No se encontro Python.
  echo Instala Python 3.12 desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Usando Python: %PY%
%PY% --version

rem --- Entorno virtual con dependencias ---
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual .venv ...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)
set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

rem --- Calidad: lint + pruebas automaticas ---
echo.
echo Revisando estilo (ruff)...
"%VPY%" -m ruff check .
if errorlevel 1 goto :error
echo Ejecutando pruebas...
"%VPY%" -m pytest
if errorlevel 1 goto :error

rem --- Ejecutable ---
echo.
echo Generando ejecutable con PyInstaller...
"%VPY%" -m PyInstaller packaging\PuntoDeVenta.spec --noconfirm --clean
if errorlevel 1 goto :error

echo.
echo ==================================================
echo  LISTO: dist\PuntoDeVentaMASTER\PuntoDeVentaMASTER.exe
echo ==================================================

rem --- Instalador (opcional, requiere Inno Setup 6 gratuito) ---
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :instalador
echo.
echo Para generar un instalador setup.exe instala Inno Setup 6 (gratis):
echo https://jrsoftware.org/isdl.php  y vuelve a ejecutar este archivo.
goto :fin

:instalador
echo.
echo Generando instalador con Inno Setup...
for /f %%v in ('"%VPY%" -c "import app; print(app.__version__)"') do set "VER=%%v"
"%ISCC%" /DAppVersion=%VER% packaging\installer.iss
if errorlevel 1 goto :error
echo Instalador creado en la carpeta "instalador".

:fin
echo.
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Revisa los mensajes de arriba.
pause
exit /b 1
