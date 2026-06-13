@echo off
chcp 65001 >nul
echo ==========================================
echo   AI股票顾问 - 每日手动执行
echo   %date% %time%
echo ==========================================
echo.

cd /d %~dp0

echo [1/4] 爬取最新新闻...
python -c "import sys; sys.path.append('.'); from app.crawler.policy_crawler import crawl_all_sources; crawl_all_sources()"
echo.

echo [2/4] 执行每日选股...
python -c "import sys; sys.path.append('.'); from app.screening.engine import run_screening; results = run_screening(); print(f'推荐 {len(results)} 只股票')"
echo.

echo [3/4] 跟踪历史推荐表现...
python -c "import sys; sys.path.append('.'); from app.learning.tracker import track_recommendations; track_recommendations()"
echo.

echo [4/4] 检查卖出信号...
python -c "import sys; sys.path.append('.'); from app.screening.signals import check_all_holdings; check_all_holdings()"
echo.

echo ==========================================
echo   执行完成！
echo ==========================================
pause