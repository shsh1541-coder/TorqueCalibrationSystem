@echo off
REM Build TorqueCalibration.exe and TorqueCalibration_Windows.zip (run on Windows 10/11).
REM   build_windows.bat               native build
REM   set SKIP_TESTS=1 & build_windows.bat
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python 3.11+ is required on the BUILD machine only. & goto :err)
python -c "import sys; assert sys.version_info >= (3, 11)" || (echo Python 3.11+ required & goto :err)

if not exist .venv-build (
  python -m venv .venv-build || goto :err
)
call .venv-build\Scripts\activate.bat || goto :err
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || goto :err

if not "%SKIP_TESTS%"=="1" (
  echo ==^> Running tests
  set QT_QPA_PLATFORM=offscreen
  python -m pytest -q tests || goto :err
  set QT_QPA_PLATFORM=
)

echo ==^> Building TorqueCalibration.exe
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name TorqueCalibration ^
  --icon resources\icons\app.ico ^
  --add-data "resources;resources" ^
  --collect-submodules pyqtgraph ^
  --exclude-module tkinter --exclude-module matplotlib ^
  --exclude-module PyQt5 --exclude-module PyQt6 ^
  main.py || goto :err

echo ==^> Creating TorqueCalibration_Windows.zip
if exist TorqueCalibration_Windows.zip del TorqueCalibration_Windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\TorqueCalibration.exe','README.md','docs\USER_MANUAL.md' -DestinationPath 'TorqueCalibration_Windows.zip' -Force" || goto :err
echo ==^> Done: dist\TorqueCalibration.exe  -^>  TorqueCalibration_Windows.zip
exit /b 0

:err
echo BUILD FAILED
exit /b 1
