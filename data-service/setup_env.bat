@echo off
echo ========================================
echo AI股票顾问环境配置脚本
echo ========================================
echo.

echo 1. 设置环境变量（当前会话有效）
echo.
echo 设置LLM_API_KEY（DeepSeek API密钥）
echo 获取地址: https://platform.deepseek.com/api_keys
set /p LLM_API_KEY="请输入DeepSeek API密钥: "
if "%LLM_API_KEY%"=="" (
    echo 未输入API密钥，跳过LLM配置
    set LLM_API_KEY=
) else (
    echo 设置环境变量LLM_API_KEY...
    setx LLM_API_KEY "%LLM_API_KEY%" > nul
)

echo.
echo 2. 检查Python环境
python --version

echo.
echo 3. 检查PyTorch安装
python -c "import torch; print(f'PyTorch版本: {torch.__version__}'); print(f'CUDA可用: {torch.cuda.is_available()}')"

echo.
echo 4. 检查数据库连接
python -c "
import os
import sys
sys.path.append('.')
try:
    from app.db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1')
    print('数据库连接: ✅ 正常')
    conn.close()
except Exception as e:
    print(f'数据库连接: ❌ 失败 - {e}')
"

echo.
echo 5. 运行功能测试
python test_extensions.py

echo.
echo ========================================
echo 配置完成！
echo.
echo 重要提醒:
echo 1. 新环境变量需要重启命令行才能生效
echo 2. 如果需要持久化环境变量，请手动添加到系统环境变量
echo 3. 首次运行会下载Kronos模型权重(~10-400MB)
echo.
echo 常用命令:
echo   运行爬虫: python -m app.crawler.policy_crawler
echo   运行选股: python -c "from app.screening.engine import run_screening; run_screening()"
echo   查看推荐: python -c "from app.screening.engine import get_today_recommendations; print(get_today_recommendations())"
echo ========================================
pause