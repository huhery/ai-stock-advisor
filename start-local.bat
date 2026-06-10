@echo off
echo ============================================
echo   AI 股票助手 - 本地启动
echo   数据库: 腾讯云 MySQL
echo ============================================
echo.

:: 检查 Redis（本地需要装 Redis，或者也指向云端）
echo [1/3] 检查 Redis...
where redis-server >nul 2>&1
if %errorlevel% neq 0 (
    echo   Redis 未安装，将跳过 Redis（部分缓存功能可能受影响）
    echo   如需安装: https://github.com/microsoftarchive/redis/releases
) else (
    start /B redis-server
    echo   Redis 已启动
)
echo.

:: 启动 Python 数据服务
echo [2/3] 启动 Python 数据服务 (端口 8001)...
start "AI-Stock-DataService" cmd /k "cd /d E:\work\ai\ai-stock-advisor\data-service && pip install -r requirements.txt -q && python -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
timeout /t 5 /nobreak >nul
echo   Python 数据服务已启动
echo.

:: 启动 Java 后端
echo [3/3] 启动 Java 后端 (端口 8080)...
start "AI-Stock-Backend" cmd /k "cd /d E:\work\ai\ai-stock-advisor\backend && mvn spring-boot:run"
timeout /t 10 /nobreak >nul
echo   Java 后端已启动
echo.

:: 启动前端
echo [4/4] 启动 Vue 前端 (端口 5173)...
start "AI-Stock-Frontend" cmd /k "cd /d E:\work\ai\ai-stock-advisor\frontend && npm install && npm run dev"
timeout /t 5 /nobreak >nul
echo   前端已启动
echo.

echo ============================================
echo   全部服务已启动！
echo   前端: http://localhost:5173
echo   后端: http://localhost:8080
echo   数据服务: http://localhost:8001
echo ============================================
echo.
echo   按任意键关闭此窗口（服务会继续在各自窗口运行）
pause >nul
