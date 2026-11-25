@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto :failed
)
set "PY=.venv\Scripts\python.exe"
"%PY%" -c "from api.main import app" >nul 2>nul
if errorlevel 1 (
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)
for %%F in (three\three.module.js three\three.core.js three\OrbitControls.js examples\simple_floorplan.json examples\residential_floorplan.json) do (
    if not exist "frontend\assets\%%F" goto :assets
)
goto :serve
:assets
call pnpm install --frozen-lockfile
if errorlevel 1 goto :failed
node scripts\prepare-viewer.mjs
if errorlevel 1 goto :failed
:serve
"%PY%" -m scripts.serve_local
if errorlevel 1 goto :failed
exit /b 0
:failed
echo Echec du lancement. Consultez les instructions dans README.md.
pause
exit /b 1
