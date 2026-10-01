@echo off
setlocal
rem Instala el sistema desde el codigo fuente (alternativa al instalador .exe).
rem Requiere Python 3.11 o superior (se recomienda 3.12) e internet SOLO durante este paso.
rem Crea el entorno .venv, instala las dependencias y deja un acceso directo en el Escritorio.
cd /d "%~dp0.."
title Instalar Punto de Venta MASTER (desde codigo)

set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] No se encontro Python.
  echo Instala Python 3.12 desde https://www.python.org/downloads/ marcando "Add python.exe to PATH"
  echo y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
echo Usando Python: %PY%
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo [ERROR] Se necesita Python 3.11 o superior.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo Creando entorno virtual .venv ...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Creando acceso directo en el Escritorio...
set "RAIZ=%CD%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Punto de Venta MASTER.lnk'); $s.TargetPath='%RAIZ%\.venv\Scripts\pythonw.exe'; $s.Arguments='-m app.main'; $s.WorkingDirectory='%RAIZ%'; $s.IconLocation='%RAIZ%\packaging\icono.ico'; $s.Save()"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Punto de Venta MASTER (navegador).lnk'); $s.TargetPath='%RAIZ%\.venv\Scripts\pythonw.exe'; $s.Arguments='-m app.main --browser'; $s.WorkingDirectory='%RAIZ%'; $s.IconLocation='%RAIZ%\packaging\icono.ico'; $s.Save()"

echo.
echo ==================================================
echo  LISTO. Abre "Punto de Venta MASTER" desde el Escritorio.
echo  Esta carpeta ^(%RAIZ%^) debe conservarse: ahi vive el programa.
echo  Los datos se guardan aparte, en %%LOCALAPPDATA%%\PuntoDeVentaMASTER
echo ==================================================
pause
exit /b 0

:error
echo.
echo [ERROR] Algo fallo. Revisa los mensajes de arriba ^(conexion a internet, permisos^).
pause
exit /b 1
