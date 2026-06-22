@echo off
echo 正在停止 AI 股票助手的本地服务...

:: 按窗口标题关闭（start-local.bat 启动的三个命名窗口）
taskkill /FI "WINDOWTITLE eq AI-Stock-DataService*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-Stock-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-Stock-Frontend*" /F >nul 2>&1

:: 兜底：按端口关闭仍在监听 8001/8080/5173 的进程
:: （只精准关闭这三个端口，不会误杀机器上其它 java/node 进程）
for %%P in (8001 8080 5173) do (
    for /f "tokens=5" %%i in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo   关闭占用端口 %%P 的进程 PID=%%i
        taskkill /F /PID %%i >nul 2>&1
    )
)

echo 所有服务已停止
pause
