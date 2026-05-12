@echo off
echo Building sidecar with PyInstaller...
cd /d "%~dp0"
pip install pyinstaller
pyinstaller --clean sidecar.spec
echo Build complete: dist\quickscan-sidecar\
