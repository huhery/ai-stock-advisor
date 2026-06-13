"""修复新闻爬虫问题

从日志看有以下问题：
1. 网络限制：Reuters、CNBC等国际网站访问受限
2. 反爬机制：网站返回401、403状态码
3. Playwright配置：需要安装浏览器
"""

import sys
import os
sys.path.append('.')

def diagnose_crawler_issues():
    """诊断爬虫问题"""
    print("=== 新闻爬虫问题诊断 ===\n")
    
    # 1. 检查网络连接
    print("1. 网络连接测试:")
    import requests
    import urllib.request
    
    test_sites = [
        ("百度", "http://www.baidu.com"),
        ("东方财富", "http://www.eastmoney.com"),
        ("新浪财经", "http://finance.sina.com.cn"),
        ("GitHub", "https://github.com"),
    ]
    
    for name, url in test_sites:
        try:
            response = requests.get(url, timeout=10)
            print(f"  ✅ {name}: 可访问 (状态码: {response.status_code})")
        except Exception as e:
            print(f"  ❌ {name}: 不可访问 - {str(e)[:100]}")
    
    # 2. 检查Playwright
    print("\n2. Playwright浏览器检查:")
    try:
        from playwright.sync_api import sync_playwright
        print("  ✅ Playwright库已安装")
        
        # 检查浏览器是否已安装
        browser_dir = r"C:\Users\Administrator\AppData\Local\ms-playwright"
        if os.path.exists(browser_dir):
            print(f"  ✅ Playwright浏览器目录存在: {browser_dir}")
            browsers = os.listdir(browser_dir)
            print(f"    已安装浏览器: {browsers}")
        else:
            print(f"  ❌ Playwright浏览器目录不存在")
            print("     请运行: playwright install")
            
    except ImportError:
        print("  ❌ Playwright库未安装")
        print("     请安装: pip install playwright")
        print("     然后运行: playwright install")
    
    # 3. 检查代理设置
    print("\n3. 代理设置检查:")
    import urllib.request
    proxies = urllib.request.getproxies()
    if proxies:
        print(f"  系统代理设置: {proxies}")
    else:
        print("  未检测到代理设置")
    
    # 4. 检查新闻源可用性
    print("\n4. 新闻源可用性:")
    from app.crawler.policy_crawler import SOURCES
    print(f"  配置了 {len(SOURCES)} 个新闻源:")
    for name, config in SOURCES.items():
        category = config.get('category', 'unknown')
        language = config.get('language', 'unknown')
        url = config.get('url', '')
        print(f"    - {name} ({category}, {language}): {url[:50]}...")
    
    # 5. 检查依赖
    print("\n5. 依赖库检查:")
    try:
        from app.crawler.scrapling_client import fetch_url
        print("  ✅ scrapling_client 模块正常")
    except Exception as e:
        print(f"  ❌ scrapling_client 导入失败: {e}")

def create_fixed_crawler():
    """创建修复后的爬虫配置"""
    print("\n=== 创建修复方案 ===\n")
    
    # 新的新闻源配置（使用可访问的网站）
    new_sources_config = """
# ===== 修复后的新闻源配置 =====
# 使用可访问的网站，避免网络限制

FIXED_SOURCES = {
    # === 国内财经 ===
    '东方财富': {
        'url': 'https://finance.eastmoney.com/news/',
        'parser': 'parse_eastmoney',
        'category': 'domestic',
        'language': 'zh',
    },
    '新浪财经': {
        'url': 'https://finance.sina.com.cn/',
        'parser': 'parse_sina',
        'category': 'domestic', 
        'language': 'zh',
    },
    '同花顺': {
        'url': 'https://news.10jqka.com.cn/',
        'parser': 'parse_ths',
        'category': 'domestic',
        'language': 'zh',
    },
    # === 国内政策 ===
    '中国政府网': {
        'url': 'http://www.gov.cn/',
        'parser': 'parse_gov_simple',
        'category': 'policy',
        'language': 'zh',
    },
    '财联社': {
        'url': 'https://www.cls.cn/',
        'parser': 'parse_cls',
        'category': 'domestic',
        'language': 'zh',
    },
    # === 国际新闻（使用中文网站） ===
    '华尔街见闻': {
        'url': 'https://wallstreetcn.com/live',
        'parser': 'parse_wallstreetcn',
        'category': 'international',
        'language': 'zh',
    },
    '金十数据': {
        'url': 'https://www.jin10.com/',
        'parser': 'parse_jin10',
        'category': 'international',
        'language': 'zh',
    },
    '彭博中文': {
        'url': 'https://www.bloomberg.cn/',
        'parser': 'parse_bloomberg_cn',
        'category': 'international',
        'language': 'zh',
    },
}
"""
    
    print("方案1: 使用可访问的国内新闻源")
    print("-" * 50)
    print(new_sources_config)
    
    # 创建简单爬虫函数
    simple_crawler = """
def create_simple_crawler():
    \"\"\"创建简单的新闻爬虫（不依赖Playwright）\"\"\"
    import requests
    from bs4 import BeautifulSoup
    from datetime import datetime
    
    def fetch_simple(url, timeout=10):
        \"\"\"简单的HTTP请求，添加User-Agent\"\"\"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"请求失败 {url}: {e}")
            return None
    
    def parse_general_news(html, selector='a'):
        \"\"\"通用新闻解析\"\"\"
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        items = []
        for link in soup.select(selector)[:20]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if title and len(title) > 5 and href:
                items.append({
                    'title': title,
                    'url': href if href.startswith('http') else f"https:{href}",
                    'publish_time': datetime.now()
                })
        return items
    
    return fetch_simple, parse_general_news
"""
    
    print("\n方案2: 创建简单爬虫函数")
    print("-" * 50)
    print(simple_crawler)
    
    print("\n方案3: 调整定时任务频率")
    print("-" * 50)
    print("""# 修改main.py中的定时任务
# 将每5分钟爬取改为：
# 1. 每日9:00、12:00、15:00各爬取一次
# 2. 手动触发API随时可用

# 在main.py的startup函数中修改：
scheduler.add_job(crawl_all_sources, 'cron', hour='9,12,15', id='crawl_news')
""")

def disable_auto_crawl():
    """禁用自动爬虫"""
    print("\n=== 快速解决方案 ===\n")
    
    fix_main_py = """
# 临时解决方案：注释掉自动爬虫任务
# 在 main.py 的 startup 函数中：

def startup():
    from app.crawler.policy_crawler import crawl_all_sources
    from app.learning.tracker import track_recommendations
    from app.learning.optimizer import weekly_optimize, ai_suggest_rules
    from app.screening.engine import run_screening
    from app.screening.signals import check_all_holdings

    # 暂时禁用自动爬虫（注释掉这一行）
    # scheduler.add_job(crawl_all_sources, 'interval', minutes=5, id='crawl_news')
    
    # 保持其他任务不变
    scheduler.add_job(run_screening, 'cron', hour=15, minute=35, id='daily_screening')
    scheduler.add_job(check_all_holdings, 'cron', hour=15, minute=50, id='check_sell')
    scheduler.add_job(track_recommendations, 'cron', hour=16, minute=0, id='daily_tracking')
    scheduler.add_job(weekly_optimize, 'cron', day_of_week='sun', hour=20, id='weekly_optimize')
    scheduler.add_job(ai_suggest_rules, 'cron', day_of_week='sun', hour=20, minute=30, id='ai_suggest')

    scheduler.start()
    print("定时任务已启动（已禁用自动爬虫）")
"""
    
    print("快速修复：禁用自动爬虫")
    print("-" * 50)
    print(fix_main_py)
    
    print("\n操作步骤:")
    print("1. 打开 app/main.py")
    print("2. 注释掉自动爬虫任务的那一行")
    print("3. 重启FastAPI服务")
    print("4. 使用手动API触发爬虫: POST /api/news/crawl")

def main():
    print("=" * 60)
    print("新闻爬虫问题修复工具")
    print("=" * 60)
    
    diagnose_crawler_issues()
    
    print("\n" + "=" * 60)
    print("问题分析:")
    print("-" * 60)
    print("1. 国际网站（Reuters、CNBC等）网络受限")
    print("2. Playwright需要安装浏览器")
    print("3. 网站反爬机制（401、403状态码）")
    print("4. 定时任务过于频繁（每5分钟）")
    
    create_fixed_crawler()
    disable_auto_crawl()
    
    print("\n" + "=" * 60)
    print("推荐操作:")
    print("-" * 60)
    print("1. 立即执行：禁用自动爬虫（修改main.py）")
    print("2. 中长期：使用可访问的国内新闻源替代")
    print("3. 手动触发：使用API /api/news/crawl 手动爬取")
    print("4. 测试验证：Kronos预测和选股功能已正常")

if __name__ == "__main__":
    main()