@echo off
echo 正在检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python！
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b
)

echo 正在安装依赖...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [警告] 依赖安装失败，尝试直接运行...
)

echo 正在启动机器人...
python tgtest_simple.py
pause
