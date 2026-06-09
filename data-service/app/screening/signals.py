"""买卖点信号模块

为每只推荐股生成具体的买入价、卖出条件和止盈止损位。
每日盘后检查持仓股是否触发卖出信号。
"""
from datetime import date, datetime
from app.db import get_connection
from app.stock_data.market_data import get_daily_kline, calculate_ma, calculate_macd


# ===== 默认参数 =====
DEFAULT_TAKE_PROFIT_PCT = 10.0   # 止盈 10%
DEFAULT_STOP_LOSS_PCT = 5.0      # 止损 5%
DEFAULT_MAX_HOLD_DAYS = 10       # 最大持有天数


def generate_buy_signal(stock_code, current_price, kline_df):
    """生成买入信号

    Args:
        stock_code: 股票代码
        current_price: 当前价格
        kline_df: K线数据

    Returns:
        dict: 买入信号详情
    """
    if kline_df.empty or len(kline_df) < 20:
        return {
            'buy_price': current_price,
            'buy_type': '收盘价买入',
            'take_profit_price': round(current_price * (1 + DEFAULT_TAKE_PROFIT_PCT / 100), 2),
            'stop_loss_price': round(current_price * (1 - DEFAULT_STOP_LOSS_PCT / 100), 2),
            'max_hold_days': DEFAULT_MAX_HOLD_DAYS,
            'support_level': None,
            'resistance_level': None,
        }

    df = calculate_ma(kline_df.copy())

    # 计算支撑位和压力位
    recent_low = df['最低'].tail(10).min()
    recent_high = df['最高'].tail(10).max()
    ma20 = df['MA20'].iloc[-1] if 'MA20' in df.columns else current_price

    # 买入价：建议在支撑位附近买入
    # 如果当前价接近支撑位（在 3% 以内），直接买入
    # 否则建议回调到 MA5 附近买入
    ma5 = df['MA5'].iloc[-1] if 'MA5' in df.columns else current_price
    if current_price <= recent_low * 1.03:
        buy_price = current_price
        buy_type = '接近支撑位，当前价买入'
    elif current_price > ma5 * 1.02:
        buy_price = round(ma5, 2)
        buy_type = f'建议回调至 MA5（{round(ma5, 2)}）附近买入'
    else:
        buy_price = current_price
        buy_type = '收盘价买入'

    # 止盈位：取压力位和固定止盈的较小值
    take_profit_by_pct = round(buy_price * (1 + DEFAULT_TAKE_PROFIT_PCT / 100), 2)
    take_profit_by_resistance = round(recent_high * 0.98, 2)  # 接近前高时考虑止盈
    take_profit_price = min(take_profit_by_pct, take_profit_by_resistance) \
        if take_profit_by_resistance > buy_price else take_profit_by_pct

    # 止损位：取支撑位和固定止损的较大值
    stop_loss_by_pct = round(buy_price * (1 - DEFAULT_STOP_LOSS_PCT / 100), 2)
    stop_loss_by_support = round(recent_low * 0.98, 2)  # 跌破支撑再下 2%
    stop_loss_price = max(stop_loss_by_pct, stop_loss_by_support)

    return {
        'buy_price': round(buy_price, 2),
        'buy_type': buy_type,
        'take_profit_price': round(take_profit_price, 2),
        'stop_loss_price': round(stop_loss_price, 2),
        'max_hold_days': DEFAULT_MAX_HOLD_DAYS,
        'support_level': round(recent_low, 2),
        'resistance_level': round(recent_high, 2),
    }


def check_sell_signal(stock_code, buy_price, buy_date, kline_df):
    """检查是否触发卖出信号

    优先级：
    1. 技术信号（MA 死叉、MACD 顶背离、跌破 MA20）
    2. 止盈止损
    3. 最大持有天数

    Args:
        stock_code: 股票代码
        buy_price: 买入价
        buy_date: 买入日期
        kline_df: 最新K线数据

    Returns:
        dict or None: 卖出信号（None 表示继续持有）
    """
    if kline_df.empty or len(kline_df) < 5:
        return None

    current_price = kline_df['收盘'].iloc[-1]
    change_pct = round((current_price - buy_price) / buy_price * 100, 2)

    df = calculate_ma(kline_df.copy())
    df = calculate_macd(df)

    # === 1. 技术信号卖出 ===

    # MA5 下穿 MA20（死叉）
    if len(df) >= 2 and 'MA5' in df.columns and 'MA20' in df.columns:
        ma5_today = df['MA5'].iloc[-1]
        ma5_yesterday = df['MA5'].iloc[-2]
        ma20_today = df['MA20'].iloc[-1]
        ma20_yesterday = df['MA20'].iloc[-2]

        if ma5_today < ma20_today and ma5_yesterday >= ma20_yesterday:
            return {
                'sell_price': round(current_price, 2),
                'sell_type': '技术信号：MA5 死叉 MA20',
                'change_pct': change_pct,
                'profit': round(current_price - buy_price, 2),
            }

    # MACD 死叉（DIF 下穿 DEA，且在零轴上方 → 高位死叉更危险）
    if len(df) >= 2 and 'DIF' in df.columns and 'DEA' in df.columns:
        dif_today = df['DIF'].iloc[-1]
        dif_yesterday = df['DIF'].iloc[-2]
        dea_today = df['DEA'].iloc[-1]
        dea_yesterday = df['DEA'].iloc[-2]

        if dif_today < dea_today and dif_yesterday >= dea_yesterday and dif_today > 0:
            return {
                'sell_price': round(current_price, 2),
                'sell_type': '技术信号：MACD 高位死叉',
                'change_pct': change_pct,
                'profit': round(current_price - buy_price, 2),
            }

    # 跌破 MA20（趋势破位）
    if 'MA20' in df.columns:
        ma20 = df['MA20'].iloc[-1]
        if current_price < ma20 * 0.98:  # 跌破 MA20 的 2% 以下
            return {
                'sell_price': round(current_price, 2),
                'sell_type': '技术信号：跌破 MA20 支撑',
                'change_pct': change_pct,
                'profit': round(current_price - buy_price, 2),
            }

    # === 2. 止盈止损 ===

    if change_pct >= DEFAULT_TAKE_PROFIT_PCT:
        return {
            'sell_price': round(current_price, 2),
            'sell_type': f'止盈触发（+{change_pct}%）',
            'change_pct': change_pct,
            'profit': round(current_price - buy_price, 2),
        }

    if change_pct <= -DEFAULT_STOP_LOSS_PCT:
        return {
            'sell_price': round(current_price, 2),
            'sell_type': f'止损触发（{change_pct}%）',
            'change_pct': change_pct,
            'profit': round(current_price - buy_price, 2),
        }

    # === 3. 最大持有天数 ===
    if isinstance(buy_date, str):
        buy_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
    hold_days = (date.today() - buy_date).days
    if hold_days >= DEFAULT_MAX_HOLD_DAYS:
        return {
            'sell_price': round(current_price, 2),
            'sell_type': f'持有超过 {DEFAULT_MAX_HOLD_DAYS} 天，到期卖出',
            'change_pct': change_pct,
            'profit': round(current_price - buy_price, 2),
        }

    return None  # 继续持有


def check_all_holdings():
    """检查所有持仓股是否触发卖出信号

    每日盘后执行。
    """
    print(f"[{datetime.now()}] 检查持仓卖出信号...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取所有未卖出的推荐（有买入价但无卖出记录）
            sql = """SELECT r.id, r.stock_code, r.stock_name, r.recommend_date,
                            r.buy_price, r.buy_type
                     FROM stock_recommendation r
                     WHERE r.sell_price IS NULL
                     AND r.buy_price IS NOT NULL
                     AND r.recommend_date >= DATE_SUB(CURDATE(), INTERVAL 20 DAY)"""
            cursor.execute(sql)
            holdings = cursor.fetchall()
    finally:
        conn.close()

    sell_count = 0
    for h in holdings:
        stock_code = h['stock_code']
        buy_price = float(h['buy_price'])
        buy_date = h['recommend_date']

        kline_df = get_daily_kline(stock_code, days=30)
        if kline_df.empty:
            continue

        signal = check_sell_signal(stock_code, buy_price, buy_date, kline_df)
        if signal:
            # 更新卖出信息
            update_sell_signal(h['id'], signal)
            sell_count += 1
            print(f"  {h['stock_name']}({stock_code}): {signal['sell_type']}，"
                  f"收益 {signal['change_pct']}%")

    print(f"[{datetime.now()}] 卖出信号检查完成，{sell_count} 只触发卖出")


def update_sell_signal(recommendation_id, signal):
    """更新推荐记录的卖出信息"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """UPDATE stock_recommendation
                     SET sell_price = %s, sell_type = %s,
                         sell_date = CURDATE(), profit_pct = %s
                     WHERE id = %s"""
            cursor.execute(sql, (
                signal['sell_price'], signal['sell_type'],
                signal['change_pct'], recommendation_id
            ))
        conn.commit()
    finally:
        conn.close()
