@echo off
REM Abre la ventana del Robot de Precios (sin consola).
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw "%~dp0price_robot_ui.py"
) else (
  start "" pythonw "%~dp0price_robot_ui.py"
)
