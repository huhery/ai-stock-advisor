"""行情数据采集模块

使用 AkShare 获取 A 股行情、基本面、资金流等数据。
"""
import akshare as ak
import pandas as pd
import os
import requests

# 禁用环境变量中的代理设置，避免网络连接问题
os.environ['NO_PROXY'] = '*'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['ALL_PROXY'] = ''


def get_stock_list():
    """获取全部 A 股实时行情列表"""
    try:
        df = ak.stock_zh_a_spot_em()
        return df
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return pd.DataFrame()


# 通用请求头：部分行情接口对无 UA 的请求会直接断开连接
_HTTP_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
}


def _market_prefix(stock_code):
    """根据股票代码推断交易所前缀（sh/sz/bj）"""
    if stock_code.startswith('6') or stock_code.startswith('9'):
        return 'sh'
    if stock_code.startswith('4') or stock_code.startswith('8'):
        return 'bj'
    return 'sz'


def _kline_from_sina(stock_code, days):
    """新浪历史日K接口（真实前复权数据）

    注意：东方财富接口在部分网络环境会被针对性屏蔽（RemoteDisconnected），
    新浪/腾讯接口实测可用，因此作为主数据源。
    """
    symbol = _market_prefix(stock_code) + stock_code
    # scale=240 表示日线；datalen 控制返回根数
    url = ("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=5&datalen={days}")
    headers = dict(_HTTP_HEADERS)
    headers['Referer'] = 'https://finance.sina.com.cn'
    resp = requests.get(url, headers=headers, timeout=15,
                        proxies={'http': None, 'https': None})
    if resp.status_code != 200:
        raise RuntimeError(f"新浪接口响应码 {resp.status_code}")
    data = resp.json()  # 列表：[{day, open, high, low, close, volume}, ...]
    if not data:
        raise RuntimeError("新浪接口无数据")
    rows = []
    for item in data:
        rows.append({
            '日期': item['day'],
            '开盘': float(item['open']),
            '收盘': float(item['close']),
            '最高': float(item['high']),
            '最低': float(item['low']),
            '成交量': float(item['volume']),
        })
    df = pd.DataFrame(rows)
    # 新浪按时间升序返回（最新在最后），保持升序——与 akshare 约定一致，
    # signals.py / backtester.py 依赖 iloc[-1] 为最新交易日。
    return df.reset_index(drop=True)


def _kline_from_tencent(stock_code, days):
    """腾讯历史日K接口（真实前复权数据，作为新浪的备用源）"""
    symbol = _market_prefix(stock_code) + stock_code
    url = ("http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={symbol},day,,,{days},qfq")
    resp = requests.get(url, headers=_HTTP_HEADERS, timeout=15,
                        proxies={'http': None, 'https': None})
    if resp.status_code != 200:
        raise RuntimeError(f"腾讯接口响应码 {resp.status_code}")
    data = resp.json()
    node = data.get('data', {}).get(symbol, {})
    # 前复权字段为 qfqday，无复权时退回 day
    klines = node.get('qfqday') or node.get('day')
    if not klines:
        raise RuntimeError("腾讯接口无数据")
    rows = []
    for k in klines:
        # 格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
        if len(k) >= 6:
            rows.append({
                '日期': k[0],
                '开盘': float(k[1]),
                '收盘': float(k[2]),
                '最高': float(k[3]),
                '最低': float(k[4]),
                '成交量': float(k[5]),
            })
    df = pd.DataFrame(rows)
    # 腾讯同样按时间升序返回（最新在最后），保持升序与 akshare 约定一致。
    return df.reset_index(drop=True)


def get_daily_kline(stock_code, days=60):
    """获取个股日 K 线数据（真实数据）

    数据源优先级（东方财富在当前网络被屏蔽，已弃用）：
      1. 新浪历史K线接口（主）
      2. 腾讯历史K线接口（备）
      3. 本地数据库缓存 stock_daily_price（兜底，表不存在时静默跳过）

    返回 DataFrame，列：日期/开盘/收盘/最高/最低/成交量，按日期降序（最新在前）。
    获取失败时返回空 DataFrame。

    Args:
        stock_code: 股票代码（如 '000001'）
        days: 获取最近 N 天数据
    """
    # ===== 主源：新浪 =====
    try:
        df = _kline_from_sina(stock_code, days)
        if not df.empty:
            return df
    except Exception as e:
        print(f"  [新浪] 获取 {stock_code} K线失败: {e}")

    # ===== 备源：腾讯 =====
    try:
        df = _kline_from_tencent(stock_code, days)
        if not df.empty:
            return df
    except Exception as e:
        print(f"  [腾讯] 获取 {stock_code} K线失败: {e}")

    # ===== 兜底：本地数据库缓存 =====
    try:
        from app.db import get_connection
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # 取最近 days 天后按时间升序排列（最新在最后），与主数据源一致
                sql = """SELECT trade_date, open_price, close_price, high_price, low_price, volume
                         FROM (
                             SELECT * FROM stock_daily_price
                             WHERE stock_code = %s
                             ORDER BY trade_date DESC LIMIT %s
                         ) t
                         ORDER BY trade_date ASC"""
                cursor.execute(sql, (stock_code, days))
                results = cursor.fetchall()
                if results:
                    rows = [{
                        '日期': r['trade_date'],
                        '开盘': float(r['open_price']),
                        '收盘': float(r['close_price']),
                        '最高': float(r['high_price']),
                        '最低': float(r['low_price']),
                        '成交量': float(r['volume']),
                    } for r in results]
                    return pd.DataFrame(rows)
        finally:
            conn.close()
    except Exception:
        # 缓存表可能不存在，静默跳过（不是关键路径）
        pass

    print(f"  ⚠️ 无法获取 {stock_code} 的K线数据（新浪/腾讯/缓存均失败）")
    return pd.DataFrame()


def get_stock_sector(stock_code):
    """获取个股所属板块（申万行业分类）"""
    try:
        df = ak.stock_board_industry_name_em()
        # 简化处理：从实时行情中获取板块信息
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot['代码'] == stock_code]
        if not row.empty:
            return row.iloc[0].get('板块', '未知')
    except Exception:
        pass
    return '未知'


def get_stock_name(stock_code):
    """获取股票名称（真实数据，腾讯接口优先，新浪兜底）

    东方财富/akshare 在当前网络被屏蔽，故改用腾讯+新浪接口。
    返回股票中文名称，失败时返回 None（由调用方决定降级策略）。
    """
    prefix = _market_prefix(stock_code)
    symbol = prefix + stock_code

    # 腾讯接口：v_sh601658="1~邮储银行~601658~..."
    try:
        url = f"http://qt.gtimg.cn/q={symbol}"
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=10,
                            proxies={'http': None, 'https': None})
        if resp.status_code == 200 and '~' in resp.text:
            parts = resp.text.split('~')
            if len(parts) >= 2 and parts[1]:
                return parts[1]
    except Exception as e:
        print(f"  [腾讯] 获取 {stock_code} 名称失败: {e}")

    # 新浪接口：var hq_str_sh601658="邮储银行,..."
    try:
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = dict(_HTTP_HEADERS)
        headers['Referer'] = 'https://finance.sina.com.cn'
        resp = requests.get(url, headers=headers, timeout=10,
                            proxies={'http': None, 'https': None})
        if resp.status_code == 200 and '="' in resp.text:
            payload = resp.text.split('="', 1)[1]
            name = payload.split(',')[0]
            if name:
                return name
    except Exception as e:
        print(f"  [新浪] 获取 {stock_code} 名称失败: {e}")

    return None


def get_current_price(stock_code):
    """获取股票当前价（真实数据，腾讯接口）

    返回最新成交价 float，失败返回 None。
    """
    symbol = _market_prefix(stock_code) + stock_code
    try:
        url = f"http://qt.gtimg.cn/q={symbol}"
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=10,
                            proxies={'http': None, 'https': None})
        if resp.status_code == 200 and '~' in resp.text:
            parts = resp.text.split('~')
            # parts[3] 为当前价
            if len(parts) > 3 and parts[3]:
                return float(parts[3])
    except Exception as e:
        print(f"  [腾讯] 获取 {stock_code} 当前价失败: {e}")
    return None


def get_fund_flow_rank():
    """获取资金流向排行（主力净流入 Top）"""
    try:
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        return df.head(100)
    except Exception as e:
        print(f"获取资金流向失败: {e}")
        return pd.DataFrame()


def get_north_fund():
    """获取北向资金数据"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(indicator="沪股通")
        return df.tail(5)
    except Exception as e:
        print(f"获取北向资金失败: {e}")
        return pd.DataFrame()


def calculate_ma(df, periods=(5, 10, 20)):
    """计算均线"""
    for p in periods:
        df[f'MA{p}'] = df['收盘'].rolling(p).mean()
    return df


def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算 MACD"""
    ema_fast = df['收盘'].ewm(span=fast).mean()
    ema_slow = df['收盘'].ewm(span=slow).mean()
    df['DIF'] = ema_fast - ema_slow
    df['DEA'] = df['DIF'].ewm(span=signal).mean()
    df['MACD'] = (df['DIF'] - df['DEA']) * 2
    return df
