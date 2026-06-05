@echo off
chcp 65001 >nul
echo ===================================
echo  AI 股票助手 - 打包部署安装包
echo ===================================
echo.

set "PROJECT_DIR=%~dp0.."
set "OUTPUT_DIR=%~dp0output"
set "TEMP_DIR=%TEMP%\ai-stock-advisor-deploy"
set "ARCHIVE_NAME=ai-stock-advisor-deploy.tar.gz"

:: 清理临时目录
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

echo [1/6] 复制部署文件...
xcopy "%~dp0install.sh" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0config.env" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0docker-compose.prod.yml" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0scripts" "%TEMP_DIR%\scripts\" /E /Y /Q >nul
xcopy "%~dp0mysql" "%TEMP_DIR%\mysql\" /E /Y /Q >nul
xcopy "%~dp0redis" "%TEMP_DIR%\redis\" /E /Y /Q >nul

echo [2/6] 复制后端源码...
xcopy "%PROJECT_DIR%\backend\Dockerfile" "%TEMP_DIR%\backend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\backend\pom.xml" "%TEMP_DIR%\backend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\backend\src" "%TEMP_DIR%\backend\src\" /E /Y /Q >nul

echo [3/6] 复制数据服务源码...
xcopy "%PROJECT_DIR%\data-service\Dockerfile" "%TEMP_DIR%\data-service\" /Y /Q >nul
xcopy "%PROJECT_DIR%\data-service\requirements.txt" "%TEMP_DIR%\data-service\" /Y /Q >nul
xcopy "%PROJECT_DIR%\data-service\app" "%TEMP_DIR%\data-service\app\" /E /Y /Q >nul

echo [4/6] 复制前端源码...
xcopy "%PROJECT_DIR%\frontend\Dockerfile" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\package.json" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\vite.config.js" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\index.html" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\nginx.conf" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\src" "%TEMP_DIR%\frontend\src\" /E /Y /Q >nul

echo [5/6] 复制 SQL...
xcopy "%PROJECT_DIR%\sql" "%TEMP_DIR%\sql\" /E /Y /Q >nul

echo [6/6] 打包为 tar.gz...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: 使用 tar（Windows 10+ 内置）
tar -czf "%OUTPUT_DIR%\%ARCHIVE_NAME%" -C "%TEMP%" ai-stock-advisor-deploy

:: 清理
rmdir /s /q "%TEMP_DIR%"

echo.
echo ===================================
echo  打包完成！
echo  输出: %OUTPUT_DIR%\%ARCHIVE_NAME%
echo ===================================
echo.
echo 使用方法:
echo   1. 将 %ARCHIVE_NAME% 上传到服务器
echo   2. tar -xzf %ARCHIVE_NAME%
echo   3. cd ai-stock-advisor-deploy
echo   4. vi config.env  (填写 LLM_API_KEY)
echo   5. bash install.sh
echo.
pause
