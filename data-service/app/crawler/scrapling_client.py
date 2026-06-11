"""Scrapling 请求客户端封装模块

统一封装 Fetcher → StealthyFetcher 降级逻辑。
所有爬虫模块通过此模块发起 HTTP 请求，替代原来的 requests 库。

@author honghui
@version 1.0
@date 2026/06/11
"""
import json
from datetime import datetime
from scrapling.fetchers import Fetcher, StealthyFetcher


def fetch_url(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回 HTML 字符串

    降级策略：
    1. Fetcher(impersonate='chrome') + stealthy_headers
    2. Fetcher(impersonate='firefox') + stealthy_headers
    3. StealthyFetcher(headless=True)

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return HTML 字符串，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：Fetcher + Chrome 指纹
    result = _try_fetcher(url, impersonate='chrome', timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + Firefox 指纹
    result = _try_fetcher(url, impersonate='firefox', timeout=timeout)
    if result is not None:
        return result

    # 第 3 层：StealthyFetcher（真实浏览器）
    result = _try_stealthy(url, timeout=30)
    if result is not None:
        return result

    return None


def fetch_json(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回解析后的 JSON dict

    降级策略与 fetch_url 相同，额外做 JSON 解析。

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return dict，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：Fetcher + Chrome 指纹
    result = _try_fetcher_json(url, impersonate='chrome', timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + Firefox 指纹
    result = _try_fetcher_json(url, impersonate='firefox', timeout=timeout)
    if result is not None:
        return result

    # 第 3 层：StealthyFetcher — 获取页面文本后尝试 JSON 解析
    text = _try_stealthy(url, timeout=30)
    if text is not None:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _try_fetcher(url, impersonate='chrome', timeout=15):
    """尝试使用 Fetcher 获取 URL，返回文本或 None

    @param url 目标 URL
    @param impersonate 模拟的浏览器指纹
    @param timeout 超时时间
    @return 页面文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200:
            return page.text
        _log(f"Fetcher({impersonate}) 状态码异常: {page.status if page else 'None'}", url)
    except Exception as e:
        _log(f"Fetcher({impersonate}) 失败: {e}", url)
    return None


def _try_fetcher_json(url, impersonate='chrome', timeout=15):
    """尝试使用 Fetcher 获取 JSON，返回 dict 或 None

    @param url 目标 URL
    @param impersonate 模拟的浏览器指纹
    @param timeout 超时时间
    @return dict 或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200:
            text = page.text
            if text:
                return json.loads(text)
        _log(f"Fetcher({impersonate}) JSON 状态码: {page.status if page else 'None'}", url)
    except json.JSONDecodeError as e:
        _log(f"Fetcher({impersonate}) JSON 解析失败: {e}", url)
    except Exception as e:
        _log(f"Fetcher({impersonate}) JSON 请求失败: {e}", url)
    return None


def _try_stealthy(url, timeout=30):
    """使用 StealthyFetcher 获取页面内容

    @param url 目标 URL
    @param timeout 超时时间
    @return 页面 HTML 文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        _log("降级使用 StealthyFetcher...", url)
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        if page:
            return page.html_content
    except Exception as e:
        _log(f"StealthyFetcher 失败: {e}", url)
    return None


def _log(message, url=''):
    """输出日志

    @param message 日志内容
    @param url 相关 URL
    @author honghui
    @date 2026/06/11 10:00
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    url_short = url[:60] + '...' if len(url) > 60 else url
    print(f"[{timestamp}] [scrapling_client] {message} | {url_short}")
