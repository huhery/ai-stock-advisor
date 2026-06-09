"""选股规则实现

每条规则接收股票数据，返回 0-100 分。
"""
import pandas as pd
from app.stock_data.market_data import calculate_ma, calculate_macd


def rule_ma_cross(kline_df):
    """MA5 上穿 MA20

    5日均线从下方突破20日均线，短期趋势转多信号。
    返回：0 或 85
    """
    if kline_df.empty or len(kline_df) < 21:
        return 0

    df = calculate_ma(kline_df.copy())

    ma5_today = df['MA5'].iloc[-1]
    ma5_yesterday = df['MA5'].iloc[-2]
    ma20_today = df['MA20'].iloc[-1]
    ma20_yesterday = df['MA20'].iloc[-2]

    if pd.isna(ma5_today) or pd.isna(ma20_today):
        return 0

    # 今天 MA5 > MA20，昨天 MA5 <= MA20 → 金叉
    if ma5_today > ma20_today and ma5_yesterday <= ma20_yesterday:
        return 85
    # MA5 > MA20 且 MA5 > MA10（多头排列）
    elif ma5_today > ma20_today:
        return 40
    return 0


def rule_macd_golden_cross(kline_df):
    """MACD 金叉

    DIF 从下方突破 DEA，动能转正。
    返回：0 或 80
    """
    if kline_df.empty or len(kline_df) < 30:
        return 0

    df = calculate_macd(kline_df.copy())

    dif_today = df['DIF'].iloc[-1]
    dif_yesterday = df['DIF'].iloc[-2]
    dea_today = df['DEA'].iloc[-1]
    dea_yesterday = df['DEA'].iloc[-2]

    if pd.isna(dif_today) or pd.isna(dea_today):
        return 0

    # DIF 上穿 DEA
    if dif_today > dea_today and dif_yesterday <= dea_yesterday:
        return 80
    return 0


def rule_volume_breakout(kline_df):
    """放量突破

    成交量放大至 5 日均量的 2 倍以上，且价格创近期新高。
    返回：0 或 85
    """
    if kline_df.empty or len(kline_df) < 10:
        return 0

    vol_today = kline_df['成交量'].iloc[-1]
    vol_ma5 = kline_df['成交量'].tail(6).iloc[:-1].mean()  # 前5日均量
    price_today = kline_df['收盘'].iloc[-1]
    price_max_10 = kline_df['最高'].tail(10).max()

    if vol_ma5 == 0:
        return 0

    # 放量（>2倍均量）且突破近10日高点
    if vol_today > vol_ma5 * 2 and price_today >= price_max_10 * 0.98:
        return 85
    elif vol_today > vol_ma5 * 1.5:
        return 40
    return 0


def rule_pe_reasonable(pe_value, industry_avg_pe=30):
    """PE 合理

    PE 低于行业均值，估值偏低有安全边际。
    返回：0-70
    """
    if pe_value is None or pe_value <= 0:
        return 0
    if pe_value < industry_avg_pe * 0.5:
        return 70  # 明显低估
    elif pe_value < industry_avg_pe * 0.8:
        return 50  # 偏低
    elif pe_value < industry_avg_pe:
        return 30  # 合理
    return 0


def rule_revenue_growth(revenue_growth_pct):
    """营收增长

    近一季度营收同比增长 > 10%。
    返回：0-75
    """
    if revenue_growth_pct is None:
        return 0
    if revenue_growth_pct > 30:
        return 75
    elif revenue_growth_pct > 20:
        return 60
    elif revenue_growth_pct > 10:
        return 45
    return 0


def rule_main_fund_inflow(net_inflow):
    """主力净流入

    当日主力资金净流入为正。
    返回：0-70
    """
    if net_inflow is None:
        return 0
    if net_inflow > 50000000:  # 5000万以上
        return 70
    elif net_inflow > 10000000:  # 1000万以上
        return 50
    elif net_inflow > 0:
        return 30
    return 0


def rule_policy_related(stock_sector, policy_keywords):
    """政策关联度

    最新政策关键词与个股所属行业匹配。
    返回：0-90
    """
    if not stock_sector or not policy_keywords:
        return 0

    stock_sector_lower = stock_sector.lower()
    match_count = 0
    for kw in policy_keywords:
        if kw.lower() in stock_sector_lower:
            match_count += 1

    if match_count >= 2:
        return 90
    elif match_count == 1:
        return 70
    return 0


# 规则注册表
RULE_REGISTRY = {
    'MA5上穿MA20': rule_ma_cross,
    'MACD金叉': rule_macd_golden_cross,
    '放量突破': rule_volume_breakout,
    'PE合理': rule_pe_reasonable,
    '营收增长': rule_revenue_growth,
    '主力净流入': rule_main_fund_inflow,
    '政策利好板块': rule_policy_related,
}
