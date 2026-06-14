"""估值与买卖点判断模块

基于微淼课程的市盈率 + 股息率方法：
- 买入：深证A股PE < 20 且个股PE < 15 且动态股息率 > 10年国债收益率
- 卖出：PE > 50 或 动态股息率 < 国债收益率/3
- 持有/等待：不满足买卖条件

数据来源：
- 深证A股PE：value500.com → 东方财富指数接口 → 腾讯行情（多源降级）
- 10年国债收益率：东方财富债券接口
"""
import re
import time
try:
    from curl_cffi import requests as http
    IMPERSONATE = True
except ImportError:
    import requests as http
    IMPERSONATE = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# 默认值（当所有接口获取失败时使用）
DEFAULT_MARKET_PE = 30.0
DEFAULT_BOND_YIELD = 2.5

# ===== 深证A股历史PE区间（来自微淼课程） =====
# PE < 20: 低估，适合买入
# PE 20-40: 合理区间
# PE > 40: 偏高，谨慎
# PE > 60: 严重高估，应该卖出
PE_ZONES = {
    'very_low': (0, 15),      # 极度低估
    'low': (15, 20),          # 低估，好价格区间
    'fair_low': (20, 30),     # 合理偏低
    'fair': (30, 40),         # 合理
    'high': (40, 55),         # 偏高
    'very_high': (55, 999),   # 严重高估
}


def get_market_pe():
    """获取深证A股整体市盈率

    多数据源降级策略：
    1. value500.com（微淼课程推荐的网站）
    2. 东方财富指数接口（深证A指 399107）
    3. 腾讯行情接口
    4. 兜底默认值

    Returns:
        float: 深证A股整体PE值
    """
    # 方案1：value500.com（课程推荐数据源）
    pe = _fetch_pe_from_value500()
    if pe:
        print(f"  [估值] value500.com 获取深证A股PE成功: {pe}")
        return pe

    # 方案2：东方财富指数接口
    pe = _fetch_pe_from_eastmoney()
    if pe:
        print(f"  [估值] 东方财富接口获取深证A股PE成功: {pe}")
        return pe

    # 方案3：腾讯行情获取深证成指PE
    pe = _fetch_pe_from_tencent()
    if pe:
        print(f"  [估值] 腾讯接口获取深证成指PE成功: {pe}")
        return pe

    print(f"  [估值] 所有接口均失败，使用默认深证A股PE: {DEFAULT_MARKET_PE}")
    return DEFAULT_MARKET_PE


def _fetch_pe_from_value500():
    """从 value500.com 获取深证A股整体市盈率

    该网站是微淼课程推荐的PE查看网站，提供沪深两市实时PE数据。
    """
    try:
        url = "http://value500.com/PE.asp"
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            return None

        # value500 页面中包含深证A股PE数据，格式通常是在表格或JS变量中
        text = resp.text

        # 尝试匹配深证A股PE值（页面中通常以"深证A股"标签附近有数字）
        # 方式1：匹配JS数据变量
        patterns = [
            r'深证A股[^0-9]*?(\d+\.?\d*)',           # 深证A股后面的数字
            r'szPE\s*[=:]\s*(\d+\.?\d*)',             # JS变量 szPE
            r'sz_pe\s*[=:]\s*(\d+\.?\d*)',            # JS变量 sz_pe
            r'深市[^0-9]*?市盈率[^0-9]*?(\d+\.?\d*)', # 深市市盈率
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = float(match.group(1))
                if 5 < val < 200:  # 合理范围校验
                    return round(val, 2)

        # 方式2：尝试解析表格中的数据
        # value500 的页面可能用表格展示，深证A股PE通常在第二行
        pe_matches = re.findall(r'>(\d{1,3}\.\d{1,2})<', text)
        if pe_matches:
            # 通常第二个合理范围的数值是深证A股PE
            for val_str in pe_matches:
                val = float(val_str)
                if 10 < val < 100:  # 深证A股PE合理范围
                    return round(val, 2)

    except Exception as e:
        print(f"  [估值] value500.com 请求失败: {e}")

    return None


def _fetch_pe_from_eastmoney():
    """从东方财富获取深证A指（399107）的PE

    使用东方财富实时行情推送接口。
    """
    try:
        # 深证A指 399107
        url = (
            "https://push2.eastmoney.com/api/qt/stock/get?"
            "secid=0.399107&fields=f43,f162,f167"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('data'):
                # f162 是市盈率(动态)
                pe = data['data'].get('f162')
                if pe is not None:
                    pe_val = float(pe)
                    if pe_val > 0:
                        return round(pe_val, 2)
                # f167 是市盈率(静态)
                pe = data['data'].get('f167')
                if pe is not None:
                    pe_val = float(pe)
                    if pe_val > 0:
                        return round(pe_val, 2)
    except Exception as e:
        print(f"  [估值] 东方财富接口失败: {e}")

    # 备选：深证成指 399001
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/stock/get?"
            "secid=0.399001&fields=f43,f162,f167"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('data'):
                pe = data['data'].get('f162')
                if pe is not None:
                    pe_val = float(pe)
                    if pe_val > 0:
                        return round(pe_val, 2)
    except Exception as e:
        print(f"  [估值] 东方财富备选接口失败: {e}")

    return None


def _fetch_pe_from_tencent():
    """从腾讯行情获取深证成指PE"""
    try:
        url = "http://qt.gtimg.cn/q=sz399001"
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=5, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=5)

        resp.encoding = 'gbk'
        parts = resp.text.split('~')
        # 腾讯行情中指数的PE字段在第39位
        if len(parts) > 39:
            pe_str = parts[39]
            if pe_str:
                pe_val = float(pe_str)
                if pe_val > 0:
                    return round(pe_val, 2)
    except Exception as e:
        print(f"  [估值] 腾讯接口失败: {e}")

    return None


def get_bond_yield():
    """获取中国10年期国债收益率

    数据源：东方财富债券接口 → 兜底默认值
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

    print(f"  [估值] 使用默认10年国债收益率: {DEFAULT_BOND_YIELD}%")
    return DEFAULT_BOND_YIELD


def analyze_market_pe(market_pe):
    """分析当前市场PE，给出交易建议

    基于微淼课程的PE区间判断：
    - PE < 20: 市场低估，适合买入好公司
    - PE 20-40: 合理区间，可持有，不宜追高
    - PE 40-60: 偏高区间，应谨慎，考虑减仓
    - PE > 60: 严重高估，应卖出

    Args:
        market_pe: 深证A股整体市盈率

    Returns:
        dict: 分析结果，包含 zone/level/advice/suitable_for_trading/description
    """
    if market_pe is None:
        return {
            'zone': 'unknown',
            'level': '未知',
            'pe_value': None,
            'suitable_for_buying': False,
            'suitable_for_holding': True,
            'should_sell': False,
            'advice': '无法获取市场PE数据，建议谨慎操作',
            'description': '当前无法判断市场整体估值水平，建议通过其他渠道确认后再做决策。',
        }

    if market_pe < 15:
        return {
            'zone': 'very_low',
            'level': '极度低估',
            'pe_value': market_pe,
            'suitable_for_buying': True,
            'suitable_for_holding': True,
            'should_sell': False,
            'advice': '极佳买入时机！市场严重低估，大胆买入好公司',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于历史极低区间（<15）。'
                f'市场恐慌性下跌时往往是最好的买入机会。'
                f'此时好公司的股价远低于内在价值，是财务自由投资者梦寐以求的买入时机。'
                f'建议：果断买入已选出的好公司，分批建仓。'
            ),
        }

    elif market_pe < 20:
        return {
            'zone': 'low',
            'level': '低估',
            'pe_value': market_pe,
            'suitable_for_buying': True,
            'suitable_for_holding': True,
            'should_sell': False,
            'advice': '好价格区间，适合买入好公司',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于低估区间（15-20）。'
                f'根据微淼课程标准，深证A股PE < 20 时代表整体市场价格低于价值，'
                f'投资价值较大。此时若目标公司TTM PE < 15 且股息率达标，可以买入。'
                f'建议：积极关注好公司，满足买入条件即可建仓。'
            ),
        }

    elif market_pe < 30:
        return {
            'zone': 'fair_low',
            'level': '合理偏低',
            'pe_value': market_pe,
            'suitable_for_buying': False,
            'suitable_for_holding': True,
            'should_sell': False,
            'advice': '估值合理偏低，可持有但不宜大举买入',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于合理偏低区间（20-30）。'
                f'市场价格与价值基本相符。此时不建议大举买入股票，'
                f'但如果个股PE特别有吸引力（< 12），可以小仓位买入。'
                f'已持有的好公司继续持有，等待更好的买入机会。'
                f'建议：保持耐心，可关注逆回购、货币基金等现金管理工具。'
            ),
        }

    elif market_pe < 40:
        return {
            'zone': 'fair',
            'level': '合理',
            'pe_value': market_pe,
            'suitable_for_buying': False,
            'suitable_for_holding': True,
            'should_sell': False,
            'advice': '市场估值合理，持有为主，不建议买入',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于合理区间中值（30-40）。'
                f'市场整体估值水平适中，后期涨跌都有可能。'
                f'不建议此时买入股票，已持有的好公司可以继续持有。'
                f'建议：将闲置资金做逆回购或货币基金，耐心等待好价格出现。'
            ),
        }

    elif market_pe < 55:
        return {
            'zone': 'high',
            'level': '偏高',
            'pe_value': market_pe,
            'suitable_for_buying': False,
            'suitable_for_holding': False,
            'should_sell': False,
            'advice': '市场偏高，谨慎持有，考虑逐步减仓',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于偏高区间（40-55）。'
                f'市场价格已开始高于价值，投资风险在增大。'
                f'绝对不能买入新股票。已持有的股票需要密切关注，'
                f'若持股的个股PE > 50 或动态股息率过低，应考虑卖出。'
                f'建议：逐步减仓，锁定利润。'
            ),
        }

    else:
        return {
            'zone': 'very_high',
            'level': '严重高估',
            'pe_value': market_pe,
            'suitable_for_buying': False,
            'suitable_for_holding': False,
            'should_sell': True,
            'advice': '市场严重高估，应该卖出！',
            'description': (
                f'当前深证A股PE为 {market_pe}，处于严重高估区间（>55）。'
                f'市场价格已经大幅高于价值，泡沫风险极高。'
                f'根据微淼课程标准，深证A股PE > 60 时应果断卖出。'
                f'此时投资风险很大，不能买进，只能卖出。'
                f'建议：尽快卖出持有的股票，将资金转入逆回购或货币基金。'
            ),
        }


def judge_valuation(stock_pe, market_pe, dividend_yield, bond_yield):
    """判断个股估值状态

    基于微淼课程买卖标准（2024-2026 更新版）：
    - 买入：市场PE < 20 且 个股PE < 15 且 动态股息率 > 国债收益率
    - 卖出：个股PE > 50 或 动态股息率 < 国债收益率/3
    - 持有：不满足卖出条件的已持有股
    - 等待：不满足买入条件

    2024-2026 更新：
    - 当前十年国债收益率降至2%左右（历史低位），股息率门槛相应降低
    - 红利策略成为主流，高股息优质公司估值中枢上移
    - 适当放宽市场PE条件（因为优质公司PE中枢整体上移）

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
    # 经典条件：市场PE < 20 且 个股PE < 15
    pe_ok = (market_pe is not None and market_pe < 20 and stock_pe < 15)
    # 放宽条件：市场PE < 25 但个股PE极具吸引力（< 12）
    pe_near_ok = (market_pe is not None and market_pe < 25 and stock_pe < 12)
    # 2024新增：国债收益率低于2%时，股息率>3%的高股息股也可考虑
    high_dividend_ok = (bond_yield < 2.0 and dividend_yield is not None
                        and dividend_yield > 3.0 and stock_pe < 20)

    dividend_ok = False
    if dividend_yield is not None and bond_yield > 0:
        dividend_ok = (dividend_yield > bond_yield)

    if (pe_ok or pe_near_ok) and dividend_ok:
        return 'buy'
    # 低利率环境下的补充买入条件
    if high_dividend_ok and market_pe is not None and market_pe < 25:
        return 'buy'

    # 持有（估值合理区间）
    if stock_pe < 30 and (dividend_yield is None or dividend_yield >= bond_yield * 0.5):
        return 'hold'

    return 'wait'


def get_market_analysis():
    """获取完整的市场估值分析

    一次性返回市场PE、国债收益率、以及交易建议。
    供 API 调用展示在前端。

    Returns:
        dict: 包含 market_pe, bond_yield, analysis 的完整分析结果
    """
    market_pe = get_market_pe()
    bond_yield = get_bond_yield()
    analysis = analyze_market_pe(market_pe)

    return {
        'market_pe': market_pe,
        'bond_yield': bond_yield,
        'analysis': analysis,
        'summary': {
            'pe_level': analysis['level'],
            'suitable_for_buying': analysis['suitable_for_buying'],
            'should_sell': analysis['should_sell'],
            'advice': analysis['advice'],
        }
    }
