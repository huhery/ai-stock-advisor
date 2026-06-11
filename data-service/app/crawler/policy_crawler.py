"""政策资讯爬虫模块

使用 Scrapling 爬取国内外政策及财经资讯网站，提取最新资讯入库。
数据源覆盖国务院、证监会、央行、Reuters、CNBC、SCMP、Investing.com、美联储。

@author honghui
@version 2.0
@date 2026/06/11
"""
from bs4 import BeautifulSoup
from datetime import datetime
from app.db import get_connection
from app.crawler.scrapling_client import fetch_url


# 数据源配置
SOURCES = {
    # === 国内政策 ===
    '国务院': {
        'url': 'https://www.gov.cn/zhengce/zuixin/index.htm',
        'parser': 'parse_gov_cn',
        'category': 'domestic',
        'language': 'zh',
    },
    '证监会': {
        'url': 'http://www.csrc.gov.cn/csrc/c100028/common_list.shtml',
        'parser': 'parse_csrc',
        'category': 'domestic',
        'language': 'zh',
    },
    '央行': {
        'url': 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html',
        'parser': 'parse_pbc',
        'category': 'domestic',
        'language': 'zh',
    },
    # === 国际财经 ===
    'Reuters': {
        'url': 'https://www.reuters.com/business/',
        'parser': 'parse_reuters',
        'category': 'international',
        'language': 'en',
    },
    'CNBC': {
        'url': 'https://www.cnbc.com/world/',
        'parser': 'parse_cnbc',
        'category': 'international',
        'language': 'en',
    },
    'SCMP': {
        'url': 'https://www.scmp.com/business',
        'parser': 'parse_scmp',
        'category': 'international',
        'language': 'en',
    },
    'Investing': {
        'url': 'https://www.investing.com/news/stock-market-news',
        'parser': 'parse_investing',
        'category': 'international',
        'language': 'en',
    },
    # === 美联储 ===
    'FederalReserve': {
        'url': 'https://www.federalreserve.gov/newsevents/pressreleases.htm',
        'parser': 'parse_fed',
        'category': 'fed',
        'language': 'en',
    },
}


# ========== 国内解析器 ==========

def parse_gov_cn(html, base_url='https://www.gov.cn'):
    """解析国务院最新政策页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('a[href*="/zhengce/"]')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


def parse_csrc(html, base_url='http://www.csrc.gov.cn'):
    """解析证监会页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.list_content a, .commonlist a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


def parse_pbc(html, base_url='http://www.pbc.gov.cn'):
    """解析央行页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.newslist_style a, .cate_content a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


# ========== 国际解析器 ==========

def parse_reuters(html, base_url='https://www.reuters.com'):
    """解析 Reuters Business 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        'a[data-testid*="Heading"]',
        'a[href*="/business/"]',
        'a[href*="/markets/"]',
        'h3 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_cnbc(html, base_url='https://www.cnbc.com'):
    """解析 CNBC World 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        '.Card-title a',
        'a[href*="/world/"]',
        'a[href*="/economy/"]',
        '.RiverHeadline a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_scmp(html, base_url='https://www.scmp.com'):
    """解析 South China Morning Post Business 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        'a[href*="/business/"]',
        'a[href*="/economy/"]',
        '.article-title a',
        'h2 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_investing(html, base_url='https://www.investing.com'):
    """解析 Investing.com 股市新闻页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        'a[href*="/news/stock-market-news/"]',
        '.articleItem a',
        'article a[href*="/news/"]',
        '.textDiv a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_fed(html, base_url='https://www.federalreserve.gov'):
    """解析美联储新闻发布页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        '.newsitem a',
        'a[href*="/newsevents/pressreleases/"]',
        '.row .col-xs-9 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


# ========== 解析器注册 ==========

PARSERS = {
    'parse_gov_cn': parse_gov_cn,
    'parse_csrc': parse_csrc,
    'parse_pbc': parse_pbc,
    'parse_reuters': parse_reuters,
    'parse_cnbc': parse_cnbc,
    'parse_scmp': parse_scmp,
    'parse_investing': parse_investing,
    'parse_fed': parse_fed,
}


# ========== 业务逻辑 ==========

def crawl_source(source_name, source_config):
    """爬取单个数据源

    @param source_name 数据源名称
    @param source_config 数据源配置
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    url = source_config['url']
    parser_name = source_config['parser']
    parser = PARSERS.get(parser_name)
    category = source_config.get('category', 'domestic')
    language = source_config.get('language', 'zh')

    if not parser:
        return []

    try:
        html = fetch_url(url)
        if not html:
            print(f"[{datetime.now()}] 爬取 {source_name} 失败: 无法获取页面内容")
            return []

        items = parser(html)
        # 补充 source/category/language 字段
        for item in items:
            item['source'] = source_name
            item['category'] = category
            item['language'] = language
            if 'publish_time' not in item:
                item['publish_time'] = datetime.now()

        return items
    except Exception as e:
        print(f"[{datetime.now()}] 爬取 {source_name} 失败: {e}")
        return []


def save_news(item):
    """保存资讯到数据库（去重）

    @param item 资讯 dict
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT IGNORE INTO policy_news
                     (source, title, url, publish_time, category, language)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (
                item['source'],
                item['title'],
                item['url'],
                item['publish_time'],
                item.get('category', 'domestic'),
                item.get('language', 'zh'),
            ))
        conn.commit()
    finally:
        conn.close()


def crawl_all_sources():
    """爬取所有数据源（定时任务调用）

    @author honghui
    @date 2026/06/11 10:00
    """
    total = 0
    for name, config in SOURCES.items():
        items = crawl_source(name, config)
        for item in items:
            save_news(item)
        total += len(items)
        print(f"[{datetime.now()}] {name}: {len(items)} 条")
    print(f"[{datetime.now()}] 爬取完成，共 {total} 条资讯")


def get_latest_news(limit=20):
    """获取最新资讯列表

    @param limit 返回条数
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM policy_news ORDER BY created_at DESC LIMIT %s"
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            for r in results:
                if r.get('publish_time'):
                    r['publish_time'] = r['publish_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()


def search_news(keyword, limit=20):
    """按关键词搜索资讯

    @param keyword 关键词
    @param limit 返回条数
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT * FROM policy_news
                     WHERE title LIKE %s OR keywords LIKE %s
                     ORDER BY created_at DESC LIMIT %s"""
            like_keyword = f'%{keyword}%'
            cursor.execute(sql, (like_keyword, like_keyword, limit))
            results = cursor.fetchall()
            for r in results:
                if r.get('publish_time'):
                    r['publish_time'] = r['publish_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()
