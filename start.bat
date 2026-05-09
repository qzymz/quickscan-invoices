@echo off
echo ========================================
echo   Invoice OCR System
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.7+.
    pause
    exit /b 1
)

:: Check dependencies
echo [1/2] Checking dependencies...
pip show gradio >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo Dependencies OK.
)
echo.

:: Start app
echo [2/2] Starting app...
echo URL: http://localhost:7860
echo.
python app.py
pause
