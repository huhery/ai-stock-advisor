@echo off
echo 正在停止所有服务...
taskkill /FI "WINDOWTITLE eq AI-Stock-DataService*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-Stock-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-Stock-Frontend*" /F >nul 2>&1
taskkill /IM "java.exe" /F >nul 2>&1
taskkill /IM "node.exe" /F >nul 2>&1
echo 所有服务已停止
pause
