@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import requests, bs4, lxml" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto error
)
echo Mantén esta ventana abierta para actualizar desde el monitor.
start "" "http://127.0.0.1:8766/"
".venv\Scripts\python.exe" scripts\source_refresh_server.py
goto end
:error
echo No se pudo preparar el servicio. Comprueba Python y tu conexión.
pause
:end
endlocal
