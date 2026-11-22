@echo off
cd /d "%~dp0"
echo Installing build dependencies (customtkinter, pyinstaller)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
echo Building standalone single-file AutoScribe.exe via PyInstaller...
pyinstaller --noconfirm --clean --onefile --noconsole --name AutoScribe --collect-data customtkinter main.py
if exist "dist\AutoScribe.exe" (
    copy /Y "dist\AutoScribe.exe" "AutoScribe.exe" >nul
    copy /Y "locations.json" "dist\locations.json" >nul
    copy /Y "config.json" "dist\config.json" >nul
    echo.
    echo =====================================================================
    echo SUCCESS! Standalone AutoScribe.exe has been created at:
    echo   1^) %CD%\AutoScribe.exe
    echo   2^) %CD%\dist\AutoScribe.exe
    echo =====================================================================
) else (
    echo Build failed.
)
pause
