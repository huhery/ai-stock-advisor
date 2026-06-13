@echo off
chcp 65001 >nul
echo ==========================================
echo   AI股票顾问 - 每周进化（周末执行）
echo   %date% %time%
echo ==========================================
echo.

cd /d %~dp0

echo 开始完整自动进化流程...
echo （包含：缓存补充 - 回测进化 - 策略应用 - AI分析）
echo.
python -c "import sys; sys.path.append('.'); from app.learning.auto_evolution import run_weekly_evolution; run_weekly_evolution()"
echo.

echo ==========================================
echo   进化完成！
echo ==========================================
pause