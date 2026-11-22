@echo off
cd /d "%~dp0"
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependency customtkinter...
    python -m pip install -r requirements.txt
)
start "" pythonw main.py
if errorlevel 1 python main.py
