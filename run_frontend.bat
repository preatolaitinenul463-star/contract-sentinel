@echo off
chcp 65001 >nul
echo ========================================
echo   合同哨兵 - 启动前端
echo ========================================
echo.

cd /d "%~dp0frontend"

echo [1/2] 安装依赖...
call npm install

echo [2/2] 启动前端服务...
echo.
echo ========================================
echo   前端启动中...
echo   访问地址: http://localhost:3000
echo   按 Ctrl+C 停止
echo ========================================
echo.

call npm run dev

pause
