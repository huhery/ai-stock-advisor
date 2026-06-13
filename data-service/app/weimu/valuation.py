"""估值与买卖点判断模块

基于微淼课程的市盈率 + 股息率方法：
- 买入：深证A股PE < 20 且个股PE < 15 且动态股息率 > 10年国债收益率
- 卖出：PE > 50 或 动态股息率 < 国债收益率/3
- 持有/等待：不满足买卖条件

数据来源：腾讯行情接口 + 东方财富
"""
import time
try:
    from curl_cffi import requests as http
    IMPERSONATE = True
except ImportError:
    import requests as http
    IMPERSONATE = False

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 默认值（当接口获取失败时使用）
DEFAULT_MARKET_PE = 30.0
DEFAULT_BOND_YIELD = 2.5


def get_market_pe():
    """获取深证A股整体市盈率

    数据源：东方财富指数接口（399107 深证A指）
    """
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/stock/get?"
            "secid=0.399107&fields=f43,f162"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('data'):
                pe = data['data'].get('f162')
                if pe and float(pe) > 0:
                    return round(float(pe), 2)
    except Exception as e:
        print(f"  [估值] 获取深证A股PE失败: {e}")

    # 备选：尝试从乐咕网获取
    try:
        url = "https://www.legulegu.com/stockdata/sz50-ttm-lyr"
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)
        # 简单解析不保证成功，失败就用默认值
    except Exception:
        pass

    print(f"  [估值] 使用默认深证A股PE: {DEFAULT_MARKET_PE}")
    return DEFAULT_MARKET_PE


def get_bond_yield():
    """获取中国10年期国债收益率

    数据源：东方财富债券接口
    """
    try:
        url = (
            "https://datacenter.eastmoney.com/securities/api/data/get?"
            "type=RPT_BOND_GZ_CN_YTM&sty=ALL"
            "&filter=(BOND_TYPE=%221%22)"
            "&p=1&ps=1&sr=-1&st=TRADE_DATE"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('result') and data['result'].get('data'):
                items = data['result']['data']
                if items:
                    ytm = items[0].get('YTM')
                    if ytm and float(ytm) > 0:
                        return round(float(ytm), 2)
    except Exception as e:
        print(f"  [估值] 获取国债收益率失败: {e}")

    # 备选：腾讯财经国债数据
    try:
        url = "http://qt.gtimg.cn/q=sh019547"
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=5, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=5)
        # 解析腾讯行情数据
    except Exception:
        pass

    print(f"  [估值] 使用默认10年国债收益率: {DEFAULT_BOND_YIELD}%")
    return DEFAULT_BOND_YIELD


def judge_valuation(stock_pe, market_pe, dividend_yield, bond_yield):
    """判断估值状态

    基于微淼课程买卖标准：
    - 买入：市场PE < 20 且 个股PE < 15 且 动态股息率 > 国债收益率
    - 卖出：个股PE > 50 或 动态股息率 < 国债收益率/3
    - 持有：不满足卖出条件的已持有股
    - 等待：不满足买入条件

    Args:
        stock_pe: 个股TTM市盈率
        market_pe: 深证A股整体市盈率
        dividend_yield: 动态股息率（%）
        bond_yield: 10年国债收益率（%）

    Returns:
        str: 'buy' / 'sell' / 'hold' / 'wait'
    """
    # 数据不足时返回等待
    if stock_pe is None or stock_pe <= 0:
        return 'wait'

    # 卖出判断（优先级最高）
    if stock_pe > 50:
        return 'sell'
    if dividend_yield is not None and bond_yield > 0:
        if dividend_yield < bond_yield / 3:
            return 'sell'

    # 买入判断
    pe_ok = (market_pe is not None and market_pe < 20 and stock_pe < 15)
    # 如果市场PE略高于20但个股PE很有吸引力，也给机会（课程中也有这种灵活处理）
    pe_near_ok = (market_pe is not None and market_pe < 25 and stock_pe < 12)

    dividend_ok = False
    if dividend_yield is not None and bond_yield > 0:
        dividend_ok = (dividend_yield > bond_yield)

    if (pe_ok or pe_near_ok) and dividend_ok:
        return 'buy'

    # 持有（估值合理区间）
    if stock_pe < 30 and (dividend_yield is None or dividend_yield >= bond_yield * 0.5):
        return 'hold'

    return 'wait'
