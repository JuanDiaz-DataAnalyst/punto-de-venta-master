@echo off
setlocal
rem Ejecuta la app desde el codigo fuente (modo desarrollo).
rem Argumentos opcionales: --browser  --server  --port 8765  --demo
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta scripts\build.bat o crea el entorno:
  echo   py -3.12 -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements-dev.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.main %*
