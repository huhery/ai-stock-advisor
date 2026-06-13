"""股票池 — 实时获取全A股列表

从东方财富/新浪接口实时获取沪深主板 + 创业板全部股票代码，排除 ST。
不含科创板（688）、北交所（8/4/9开头）。
"""
import requests
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 兜底池（约100只核心股票）
FALLBACK_POOL = [
    '600519', '000858', '600036', '601318', '000333', '600900', '601166', '600276', '000651', '601888',
    '300750', '002475', '600031', '601012', '600809', '000568', '002304', '600585', '601658', '002714',
    '300059', '002352', '600887', '601669', '000725', '600690', '601398', '600048', '000001', '600000',
    '601939', '601288', '601328', '600028', '601988', '600050', '601628', '601601', '600030', '000002',
    '000063', '000100', '000157', '000425', '000538', '600016', '600104', '600111', '600196', '600536',
    '600570', '600588', '600703', '600745', '600837', '601066', '601088', '601111', '601138', '601169',
    '601186', '601211', '601229', '601336', '601668', '601688', '601727', '601766', '601800', '601818',
    '601857', '601881', '601989', '601998', '603259', '603288', '603501', '603799', '603986', '603993',
    '300015', '300124', '300014', '300347', '300142', '300408', '300628', '300454', '688981', '000069',
    '000338', '000488', '000528', '000550', '000596', '000625', '000629', '000636', '000703', '000725',
    '000800', '000876', '000898', '000913', '000977', '002001', '002007', '002024', '002027', '002044',
]


def fetch_stock_pool():
    """实时获取全A股列表（沪深主板 + 创业板，排除ST）

    按优先级尝试多个数据源，确保稳定获取。
    """
    # 方案1：新浪财经（最稳定，不走HTTPS代理）
    codes = _fetch_from_sina()
    if codes and len(codes) > 500:
        print(f"  [股票池] 新浪接口获取成功: {len(codes)} 只")
        return codes

    # 方案2：东方财富 HTTP
    codes = _fetch_from_eastmoney()
    if codes and len(codes) > 500:
        print(f"  [股票池] 东方财富接口获取成功: {len(codes)} 只")
        return codes

    # 兜底
    print(f"  [警告] 实时获取股票列表失败，使用兜底池({len(FALLBACK_POOL)}只)")
    return FALLBACK_POOL


def _fetch_from_sina():
    """从新浪财经接口获取全部A股列表（最稳定）

    新浪的股票列表接口用HTTP，不受HTTPS代理限制。
    分页获取，每页80只。
    """
    all_codes = []
    page = 1
    max_pages = 80  # 约5000只股票 / 80每页 ≈ 63页

    while page <= max_pages:
        url = (
            f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"Market_Center.getHQNodeData?page={page}&num=80&sort=symbol&asc=1"
            f"&node=hs_a&symbol=&_s_r_a=page"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                break

            text = resp.text.strip()
            if not text or text == 'null' or len(text) < 10:
                break

            # 新浪返回的是JSON数组
            import json
            items = json.loads(text)
            if not items:
                break

            for item in items:
                code = item.get('code', '')
                name = item.get('name', '')
                symbol = item.get('symbol', '')

                if not code:
                    continue
                # 只保留沪深主板和创业板（60/00/30开头）
                if not (code.startswith('60') or code.startswith('00')
                        or code.startswith('30')):
                    continue
                # 排除ST
                if 'ST' in name.upper():
                    continue
                all_codes.append(code)

            page += 1
            time.sleep(0.3)  # 避免请求过快

        except Exception as e:
            if page == 1:
                print(f"  [新浪] 首页请求失败: {e}")
            break

    return all_codes


def _fetch_from_eastmoney():
    """从东方财富接口获取全部A股列表"""
    all_codes = []

    # 分开请求沪市和深市，确保筛选准确
    markets = [
        ('沪市主板', 'm:1+t:2,m:1+t:23'),   # 上海主板
        ('深市主板', 'm:0+t:6,m:0+t:80'),    # 深圳主板+中小板
        ('创业板', 'm:0+t:81'),              # 创业板
    ]

    for market_name, fs_param in markets:
        url = (
            f"http://82.push2.eastmoney.com/api/qt/clist/get"
            f"?pn=1&pz=5000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
            f"&fltt=2&invt=2&fid=f3&fs={fs_param}"
            f"&fields=f12,f14"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data.get('data', {}).get('diff', [])
            if not items:
                continue

            count = 0
            for item in items:
                code = item.get('f12', '')
                name = item.get('f14', '')
                if not code:
                    continue
                # 二次确认：只保留60/00/30开头
                if not (code.startswith('60') or code.startswith('00')
                        or code.startswith('30')):
                    continue
                # 排除ST
                if 'ST' in name.upper():
                    continue
                all_codes.append(code)
                count += 1
            time.sleep(0.3)
        except Exception:
            continue

    return all_codes


# 兼容旧代码：提供 STOCK_POOL 变量（懒加载）
class _LazyPool:
    """延迟加载的股票池，兼容 `from stock_pool import STOCK_POOL` 用法"""

    def __init__(self):
        self._data = None

    def _load(self):
        if self._data is None:
            self._data = fetch_stock_pool()
        return self._data

    def __iter__(self):
        return iter(self._load())

    def __len__(self):
        return len(self._load())

    def __contains__(self, item):
        return item in self._load()

    def __getitem__(self, index):
        return self._load()[index]

    def __repr__(self):
        return f"LazyPool({len(self._load())} stocks)"


STOCK_POOL = _LazyPool()
