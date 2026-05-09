@echo off
chcp 65001 >nul
echo ========================================
echo   发票OCR识别系统 启动脚本
echo ========================================
echo.

:: 检查 Python 是否存在
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

:: 检查依赖是否已安装
echo [1/2] 检查依赖...
pip show gradio >nul 2>&1
if errorlevel 1 (
    echo 依赖未安装，正在安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
) else (
    echo 依赖已安装
)
echo.

:: 启动应用
echo [2/2] 启动应用...
echo 访问地址: http://localhost:7860
echo.
python app.py
pause
