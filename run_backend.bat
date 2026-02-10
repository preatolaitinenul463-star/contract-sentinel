@echo off
chcp 65001 >nul
echo ========================================
echo   合同哨兵 - 启动后端
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/4] 检查 Python 虚拟环境...
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

echo [2/4] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [3/4] 安装依赖...
pip install -r requirements.txt -q

echo [4/4] 启动后端服务...
echo.
echo ========================================
echo   后端启动中...
echo   API 地址: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo   按 Ctrl+C 停止
echo ========================================
echo.

python -m uvicorn app.main:app --reload --port 8000

pause
