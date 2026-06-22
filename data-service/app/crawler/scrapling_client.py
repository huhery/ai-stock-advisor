"""HTTP 请求客户端封装模块

降级策略：requests → Fetcher(scrapling) → StealthyFetcher
所有爬虫模块通过此模块发起 HTTP 请求。

@author honghui
@version 2.0
@date 2026/06/11
"""
import json
import time
import random
import requests as _requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime

# 默认请求头，模拟正常浏览器
_DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://finance.eastmoney.com',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 带重试的 requests Session
_session = _requests.Session()
_retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_session.mount('https://', _adapter)
_session.mount('http://', _adapter)


def fetch_url(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回 HTML 字符串

    降级策略：
    1. requests + 浏览器 UA
    2. Fetcher(scrapling) + stealthy_headers
    3. StealthyFetcher(headless=True)

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return HTML 字符串，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：requests 直接请求
    result = _try_requests(url, timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + stealthy_headers
    result = _try_fetcher(url, timeout=timeout)
    if result is not None:
        return result

    # 第 3 层：StealthyFetcher（真实浏览器）
    result = _try_stealthy(url, timeout=30)
    if result is not None:
        return result

    return None


def fetch_json(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回解析后的 JSON dict

    降级策略：
    1. requests + 浏览器 UA
    2. Fetcher(scrapling) + stealthy_headers
    3. StealthyFetcher(headless=True)

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return dict/list，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：requests 直接请求
    result = _try_requests_json(url, timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + stealthy_headers
    result = _try_fetcher_json(url, timeout=timeout)
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


def _try_requests(url, timeout=15):
    """使用 requests 库获取 URL，返回文本或 None

    遇到 SSL 错误时自动重试一次（加短暂延迟）。

    @param url 目标 URL
    @param timeout 超时时间
    @return 页面文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    for attempt in range(2):
        try:
            # 禁用代理，避免代理连接问题
            proxies = {
                'http': None,
                'https': None
            }
            resp = _session.get(url, headers=_DEFAULT_HEADERS, timeout=timeout, proxies=proxies)
            if resp.status_code == 200 and resp.text:
                # 修正编码：国内政府站点多为 GBK/GB2312，requests 可能误判为 ISO-8859-1
                # 用 apparent_encoding（chardet 探测）纠正，避免中文乱码
                if resp.encoding is None or resp.encoding.lower() in ('iso-8859-1', 'ascii'):
                    detected = resp.apparent_encoding
                    if detected:
                        resp.encoding = detected
                return resp.text
            _log(f"requests 状态码: {resp.status_code}, body长度: {len(resp.text) if resp.text else 0}", url)
            return None
        except (_requests.exceptions.SSLError, _requests.exceptions.ConnectionError) as e:
            if attempt == 0:
                time.sleep(random.uniform(1, 2))
                continue
            _log(f"requests SSL/连接失败: {e}", url)
        except Exception as e:
            _log(f"requests 失败: {e}", url)
            break
    return None


def _try_requests_json(url, timeout=15):
    """使用 requests 库获取 JSON，返回 dict 或 None

    遇到 SSL 错误时自动重试一次。

    @param url 目标 URL
    @param timeout 超时时间
    @return dict/list 或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    for attempt in range(2):
        try:
            # 禁用代理，避免代理连接问题
            proxies = {
                'http': None,
                'https': None
            }
            resp = _session.get(url, headers=_DEFAULT_HEADERS, timeout=timeout, proxies=proxies)
            if resp.status_code == 200 and resp.text:
                cleaned = resp.text.strip()
                # 处理 JSONP 包裹
                if cleaned.startswith('(') and cleaned.endswith(')'):
                    cleaned = cleaned[1:-1]
                return json.loads(cleaned)
            _log(f"requests JSON 状态码: {resp.status_code}, body长度: {len(resp.text) if resp.text else 0}", url)
            return None
        except (_requests.exceptions.SSLError, _requests.exceptions.ConnectionError) as e:
            if attempt == 0:
                time.sleep(random.uniform(1, 2))
                continue
            _log(f"requests JSON SSL/连接失败: {e}", url)
        except json.JSONDecodeError as e:
            _log(f"requests JSON 解析失败: {e}", url)
            break
        except Exception as e:
            _log(f"requests JSON 请求失败: {e}", url)
            break
    return None


def _try_fetcher(url, timeout=15):
    """尝试使用 scrapling Fetcher 获取 URL，返回文本或 None

    @param url 目标 URL
    @param timeout 超时时间
    @return 页面文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200 and page.text:
            return page.text
        _log(f"Fetcher 状态码: {page.status if page else 'None'}, body为空: {not page.text if page else True}", url)
    except ImportError:
        _log("scrapling 未安装，跳过 Fetcher 层", url)
    except Exception as e:
        _log(f"Fetcher 失败: {e}", url)
    return None


def _try_fetcher_json(url, timeout=15):
    """尝试使用 scrapling Fetcher 获取 JSON，返回 dict 或 None

    @param url 目标 URL
    @param timeout 超时时间
    @return dict/list 或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200 and page.text:
            cleaned = page.text.strip()
            if cleaned.startswith('(') and cleaned.endswith(')'):
                cleaned = cleaned[1:-1]
            return json.loads(cleaned)
        _log(f"Fetcher JSON body为空 (status={page.status if page else 'None'})", url)
    except ImportError:
        _log("scrapling 未安装，跳过 Fetcher JSON 层", url)
    except json.JSONDecodeError as e:
        _log(f"Fetcher JSON 解析失败: {e}", url)
    except Exception as e:
        _log(f"Fetcher JSON 请求失败: {e}", url)
    return None


def _try_stealthy(url, timeout=30):
    """使用 StealthyFetcher 获取页面内容

    延迟导入，避免未安装 patchright 时模块加载失败。

    注意：StealthyFetcher.fetch 是同步 API，底层用 Playwright Sync。
    若当前运行在 asyncio 事件循环中（如 FastAPI 请求线程），调用会直接抛
    "Sync API inside the asyncio loop" 异常，故此处先检测事件循环并跳过，
    避免崩溃和无意义的报错日志。

    @param url 目标 URL
    @param timeout 超时时间
    @return 页面 HTML 文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 检测是否处于 asyncio 事件循环中，是则跳过（同步 Playwright 无法在事件循环内运行）
    import asyncio
    try:
        asyncio.get_running_loop()
        _log("当前处于 asyncio 事件循环，跳过 StealthyFetcher（同步API不兼容）", url)
        return None
    except RuntimeError:
        pass  # 没有运行中的事件循环，可以安全使用同步 API

    try:
        from scrapling.fetchers import StealthyFetcher
        _log("降级使用 StealthyFetcher...", url)
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        if page:
            return page.html_content
    except ImportError:
        _log("StealthyFetcher 不可用（缺少 patchright），跳过该降级层", url)
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
