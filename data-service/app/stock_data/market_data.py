"""行情数据采集模块

使用 AkShare 获取 A 股行情、基本面、资金流等数据。
"""
import akshare as ak
import pandas as pd


def get_stock_list():
    """获取全部 A 股实时行情列表"""
    try:
        df = ak.stock_zh_a_spot_em()
        return df
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return pd.DataFrame()


def get_daily_kline(stock_code, days=60):
    """获取个股日 K 线数据

    Args:
        stock_code: 股票代码（如 '000001'）
        days: 获取最近 N 天数据
    """
    try:
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            adjust="qfq"
        )
        return df.tail(days)
    except Exception as e:
        print(f"获取 {stock_code} K线失败: {e}")
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
