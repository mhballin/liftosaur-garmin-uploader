@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0"

echo 🏋️ Liftosaur → Garmin Uploader — Installer

echo Checking Python version...
set "PYTHON_CMD="
set "PY_VER="

where python >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=python"
  for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "PY_VER=%%V"
) else (
  where python3 >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=python3"
    for /f "tokens=2 delims= " %%V in ('python3 --version 2^>^&1') do set "PY_VER=%%V"
  )
)

if "%PYTHON_CMD%"=="" (
  echo ❌ Python 3.10+ is required. Python was not found. Install from https://python.org
  popd
  exit /b 1
)

for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
  set "PY_MAJOR=%%a"
  set "PY_MINOR=%%b"
)

if %PY_MAJOR% LSS 3 (
  echo ❌ Python 3.10+ is required. You have %PY_MAJOR%.%PY_MINOR%. Install from https://python.org
  popd
  exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
  echo ❌ Python 3.10+ is required. You have %PY_MAJOR%.%PY_MINOR%. Install from https://python.org
  popd
  exit /b 1
)

if exist .venv (
  set /p REINSTALL=Virtual environment already exists. Reinstall? (y/N) 
  if /I not "%REINSTALL%"=="y" (
    echo Skipping venv creation.
  ) else (
    rmdir /s /q .venv
  )
)

if not exist .venv (
  %PYTHON_CMD% -m venv .venv
)

.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .

echo ✅ Dependencies installed

set /p RUN_SETUP=Run setup wizard now? (Y/n) 
if "%RUN_SETUP%"=="" (
  .venv\Scripts\python -m liftosaur_garmin --setup
) else if /I "%RUN_SETUP%"=="y" (
  .venv\Scripts\python -m liftosaur_garmin --setup
)

echo.
echo ✅ Installation complete!
echo.
echo To use the tool, either:
echo   .venv\Scripts\activate
echo   liftosaur-garmin --help
echo.
echo Or run directly:
echo   .venv\Scripts\liftosaur-garmin --help

popd
endlocal
