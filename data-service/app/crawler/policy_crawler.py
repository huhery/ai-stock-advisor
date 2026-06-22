"""政策资讯爬虫模块

使用 Scrapling 爬取国内外政策及财经资讯网站，提取最新资讯入库。
数据源覆盖国务院、证监会、央行、Reuters、CNBC、SCMP、Investing.com、美联储。
爬取后自动调用 LLM 分析新闻对 A 股板块的影响，提取关键词和受益板块。

@author honghui
@version 2.1
@date 2026/06/11
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app.db import get_connection
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.crawler.scrapling_client import fetch_url


# 数据源配置
# enabled: 是否启用。国外财经站点（Reuters/CNBC/SCMP/Investing/Fed）在国内网络
#          普遍不可达（连接超时或 403），默认关闭，避免每次爬取被超时拖慢并刷错误日志。
#          如果部署环境有海外网络访问能力，可手动改为 True 重新启用。
SOURCES = {
    # === 国内政策（网络可达，默认启用）===
    '国务院': {
        'url': 'https://www.gov.cn/zhengce/zuixin/index.htm',
        'parser': 'parse_gov_cn',
        'category': 'domestic',
        'language': 'zh',
        # 国务院"最新政策"列表为 JS 动态渲染，普通 HTTP 请求拿不到内容，
        # 需浏览器渲染（Playwright）。暂禁用，重要政策可通过证监会转发覆盖。
        'enabled': False,
    },
    '证监会': {
        'url': 'http://www.csrc.gov.cn/csrc/c100028/list.shtml',
        'parser': 'parse_csrc',
        'category': 'domestic',
        'language': 'zh',
        'enabled': True,
    },
    '央行': {
        'url': 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html',
        'parser': 'parse_pbc',
        'category': 'domestic',
        'language': 'zh',
        'enabled': True,
    },
    # === 国际财经（国内网络不可达，默认禁用）===
    'Reuters': {
        'url': 'https://www.reuters.com/business/',
        'parser': 'parse_reuters',
        'category': 'international',
        'language': 'en',
        'enabled': False,
    },
    'CNBC': {
        'url': 'https://www.cnbc.com/world/',
        'parser': 'parse_cnbc',
        'category': 'international',
        'language': 'en',
        'enabled': False,
    },
    'SCMP': {
        'url': 'https://www.scmp.com/business',
        'parser': 'parse_scmp',
        'category': 'international',
        'language': 'en',
        'enabled': False,
    },
    'Investing': {
        'url': 'https://www.investing.com/news/stock-market-news',
        'parser': 'parse_investing',
        'category': 'international',
        'language': 'en',
        'enabled': False,
    },
    # === 美联储（国内网络不可达，默认禁用）===
    'FederalReserve': {
        'url': 'https://www.federalreserve.gov/newsevents/pressreleases.htm',
        'parser': 'parse_fed',
        'category': 'fed',
        'language': 'en',
        'enabled': False,
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
    """解析证监会新闻列表页

    数据源为 list.shtml（静态列表页，含真实新闻数据）。
    注意：原 common_list.shtml 是 JS 动态加载的空壳页，无法直接解析。

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    seen_urls = set()
    # 证监会新闻详情页链接特征：含 content.shtml
    for link in soup.select('a[href*="content"]'):
        title = link.get_text(strip=True)
        href = link.get('href', '')
        # 过滤过短标题和无效链接
        if not title or len(title) < 5:
            continue
        if 'content' not in href:
            continue
        if not href.startswith('http'):
            href = base_url + href
        # 去重（列表页存在重复链接）
        if href in seen_urls:
            continue
        seen_urls.add(href)
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 20:
            break
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


def save_news_return_new(item):
    """保存资讯到数据库，返回是否为新增记录

    @param item 资讯 dict
    @return True 如果是新增，False 如果已存在
    @author honghui
    @date 2026/06/11
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
            is_new = cursor.rowcount > 0
        conn.commit()
        return is_new
    finally:
        conn.close()


def crawl_all_sources():
    """爬取所有数据源，并对新入库的新闻进行 LLM 分析

    @author honghui
    @date 2026/06/11 10:00
    """
    total = 0
    new_items = []
    for name, config in SOURCES.items():
        # 跳过已禁用的源（如国内网络不可达的国外站点）
        if not config.get('enabled', True):
            continue
        items = crawl_source(name, config)
        for item in items:
            is_new = save_news_return_new(item)
            if is_new:
                new_items.append(item)
        total += len(items)
        print(f"[{datetime.now()}] {name}: {len(items)} 条")
    print(f"[{datetime.now()}] 爬取完成，共 {total} 条资讯，新增 {len(new_items)} 条")

    # 对新入库的新闻批量调用 LLM 分析板块影响
    if new_items:
        analyze_news_impact(new_items)



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


# ========== LLM 新闻影响分析 ==========

NEWS_ANALYSIS_PROMPT = """你是一位资深A股研究员。请分析以下新闻标题对A股市场的影响。

新闻列表：
{news_list}

请对每条新闻分析：
1. 提取中文关键词（用于匹配A股股票名称和板块概念）
2. 判断利好哪些A股板块/概念

要求：
- 关键词必须是中文，即使原始新闻是英文也要翻译为中文关键词
- 关键词应包含：行业词（如"新能源"、"半导体"）、概念词（如"降息"、"芯片"）、公司简称
- 板块使用A股常见板块名称，如：银行、地产、新能源、半导体、医药、军工、消费、有色金属、石油化工、科技、汽车等

请严格按以下JSON格式输出，不要有其他内容：
[
  {{"title": "原始标题", "keywords": "关键词1,关键词2,关键词3", "sectors": "板块1,板块2"}}
]
"""


def analyze_news_impact(news_items):
    """调用 LLM 分析新闻对 A 股板块的影响，回写 keywords 和 related_sectors

    每次最多分析 20 条新闻（控制 token 用量）。

    @param news_items 新闻列表
    @author honghui
    @date 2026/06/11
    """
    if not LLM_API_KEY:
        print("  [跳过] 未配置 LLM_API_KEY，无法分析新闻影响")
        return

    # 分批处理，每批最多 20 条
    batch_size = 20
    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]
        _analyze_batch(batch)


def _analyze_batch(batch):
    """分析一批新闻"""
    # 组装新闻列表文本
    news_text = ""
    for idx, item in enumerate(batch, 1):
        source = item.get('source', '未知')
        category = item.get('category', 'domestic')
        lang_hint = "（英文）" if item.get('language') == 'en' else ""
        news_text += f"{idx}. [{source}]{lang_hint} {item['title']}\n"

    prompt = NEWS_ANALYSIS_PROMPT.format(news_list=news_text)

    try:
        headers = {
            'Authorization': f'Bearer {LLM_API_KEY}',
            'Content-Type': 'application/json'
        }
        body = {
            'model': LLM_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.3,
        }
        resp = requests.post(
            f'{LLM_BASE_URL}/chat/completions',
            headers=headers,
            json=body,
            timeout=60
        )
        if resp.status_code != 200:
            print(f"  [LLM] 分析失败，状态码: {resp.status_code}")
            return

        content = resp.json()['choices'][0]['message']['content']
        # 提取 JSON
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            print("  [LLM] 返回内容无法解析为JSON")
            return

        results = json.loads(json_match.group())
        _update_news_analysis(batch, results)
        print(f"  [LLM] 成功分析 {len(results)} 条新闻的板块影响")

    except Exception as e:
        print(f"  [LLM] 新闻分析异常: {e}")


def _update_news_analysis(batch, results):
    """将 LLM 分析结果回写到数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for result in results:
                title = result.get('title', '')
                keywords = result.get('keywords', '')
                sectors = result.get('sectors', '')
                if not title or (not keywords and not sectors):
                    continue
                sql = """UPDATE policy_news
                         SET keywords = %s, related_sectors = %s
                         WHERE title = %s AND keywords IS NULL"""
                cursor.execute(sql, (keywords, sectors, title))
        conn.commit()
    finally:
        conn.close()
