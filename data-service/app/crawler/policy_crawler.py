"""政策资讯爬虫模块

定时爬取国家政策相关网站，提取最新政策资讯入库。
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app.db import get_connection


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 数据源配置
SOURCES = {
    '国务院': {
        'url': 'https://www.gov.cn/zhengce/zuixin/index.htm',
        'parser': 'parse_gov_cn'
    },
    '证监会': {
        'url': 'http://www.csrc.gov.cn/csrc/c100028/common_list.shtml',
        'parser': 'parse_csrc'
    },
    '央行': {
        'url': 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html',
        'parser': 'parse_pbc'
    },
}


def parse_gov_cn(html, base_url='https://www.gov.cn'):
    """解析国务院最新政策页面"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('a[href*="/zhengce/"]')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({
            'source': '国务院',
            'title': title,
            'url': href,
            'publish_time': datetime.now()
        })
    return items


def parse_csrc(html, base_url='http://www.csrc.gov.cn'):
    """解析证监会页面"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.list_content a, .commonlist a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({
            'source': '证监会',
            'title': title,
            'url': href,
            'publish_time': datetime.now()
        })
    return items


def parse_pbc(html, base_url='http://www.pbc.gov.cn'):
    """解析央行页面"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.newslist_style a, .cate_content a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({
            'source': '央行',
            'title': title,
            'url': href,
            'publish_time': datetime.now()
        })
    return items


PARSERS = {
    'parse_gov_cn': parse_gov_cn,
    'parse_csrc': parse_csrc,
    'parse_pbc': parse_pbc,
}


def crawl_source(source_name, source_config):
    """爬取单个数据源"""
    url = source_config['url']
    parser_name = source_config['parser']
    parser = PARSERS.get(parser_name)
    if not parser:
        return []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        items = parser(resp.text)
        return items
    except Exception as e:
        print(f"[{datetime.now()}] 爬取 {source_name} 失败: {e}")
        return []


def save_news(item):
    """保存资讯到数据库（去重）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT IGNORE INTO policy_news (source, title, url, publish_time)
                     VALUES (%s, %s, %s, %s)"""
            cursor.execute(sql, (
                item['source'],
                item['title'],
                item['url'],
                item['publish_time']
            ))
        conn.commit()
    finally:
        conn.close()


def crawl_all_sources():
    """爬取所有数据源（定时任务调用）"""
    total = 0
    for name, config in SOURCES.items():
        items = crawl_source(name, config)
        for item in items:
            save_news(item)
        total += len(items)
    print(f"[{datetime.now()}] 爬取完成，共 {total} 条资讯")


def get_latest_news(limit=20):
    """获取最新资讯列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM policy_news ORDER BY created_at DESC LIMIT %s"
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            # 处理 datetime 序列化
            for r in results:
                if r.get('publish_time'):
                    r['publish_time'] = r['publish_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()


def search_news(keyword, limit=20):
    """按关键词搜索资讯"""
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
