"""本地每日选股脚本

在本地 Windows 上运行，获取实时行情+K线，执行选股，结果写入远程 MySQL。
解决云服务器无法访问 AkShare 的问题。

使用方法：
    pip install akshare pymysql cryptography
    python scripts/daily_screening_local.py --host 81.69.42.239 --password AiStock2026!

定时任务设置（Windows 任务计划程序）：
    每个交易日 15:35 执行一次
"""
import time
import json
import argparse
import pymysql
import akshare as ak
import pandas as pd
from datetime import date, datetime


def get_connection(host, port, user, password, database):
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


def get_active_rules(conn):
    """获取活跃的筛选规则"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM screening_rules WHERE status = 'active'")
        return cursor.fetchall()


def get_policy_keywords(conn):
    """从最近政策中提取关键词"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT keywords, related_sectors FROM policy_news
            WHERE created_at > DATE_SUB(NOW(), INTERVAL 3 DAY)
            AND keywords IS NOT NULL
        """)
        rows = cursor.fetchall()
        keywords = set()
        for row in rows:
            if row.get('keywords'):
                for kw in row['keywords'].split(','):
                    kw = kw.strip()
                    if kw:
                        keywords.add(kw)
        return list(keywords)


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


def score_ma_cross(df):
    """MA5上穿MA20"""
    if len(df) < 21:
        return 0
    df = calculate_ma(df.copy())
    ma5_today = df['MA5'].iloc[-1]
    ma5_yesterday = df['MA5'].iloc[-2]
    ma20_today = df['MA20'].iloc[-1]
    ma20_yesterday = df['MA20'].iloc[-2]
    if pd.isna(ma5_today) or pd.isna(ma20_today):
        return 0
    if ma5_today > ma20_today and ma5_yesterday <= ma20_yesterday:
        return 85
    elif ma5_today > ma20_today:
        return 40
    return 0


def score_macd_cross(df):
    """MACD金叉"""
    if len(df) < 30:
        return 0
    df = calculate_macd(df.copy())
    dif_today = df['DIF'].iloc[-1]
    dif_yesterday = df['DIF'].iloc[-2]
    dea_today = df['DEA'].iloc[-1]
    dea_yesterday = df['DEA'].iloc[-2]
    if pd.isna(dif_today) or pd.isna(dea_today):
        return 0
    if dif_today > dea_today and dif_yesterday <= dea_yesterday:
        return 80
    return 0


def score_volume_breakout(df):
    """放量突破"""
    if len(df) < 10:
        return 0
    vol_today = df['成交量'].iloc[-1]
    vol_ma5 = df['成交量'].tail(6).iloc[:-1].mean()
    if vol_ma5 == 0:
        return 0
    if vol_today > vol_ma5 * 2:
        return 85
    elif vol_today > vol_ma5 * 1.5:
        return 40
    return 0


def score_pe(pe_value, industry_avg=30):
    """PE合理"""
    if pe_value is None or pe_value <= 0:
        return 0
    if pe_value < industry_avg * 0.5:
        return 70
    elif pe_value < industry_avg * 0.8:
        return 50
    elif pe_value < industry_avg:
        return 30
    return 0


def score_fund_flow(net_inflow):
    """主力净流入"""
    if net_inflow is None:
        return 0
    if net_inflow > 50000000:
        return 70
    elif net_inflow > 10000000:
        return 50
    elif net_inflow > 0:
        return 30
    return 0


def score_policy_related(sector, policy_keywords):
    """政策关联"""
    if not sector or not policy_keywords:
        return 0
    match = sum(1 for kw in policy_keywords if kw in sector)
    if match >= 2:
        return 90
    elif match == 1:
        return 70
    return 0


def generate_buy_signal(current_price, df):
    """生成买入信号"""
    if df.empty or len(df) < 20:
        return {
            'buy_price': current_price,
            'buy_type': '收盘价买入',
            'take_profit_price': round(current_price * 1.10, 2),
            'stop_loss_price': round(current_price * 0.95, 2),
            'support_level': None,
            'resistance_level': None,
        }

    df_ma = calculate_ma(df.copy())
    recent_low = df['最低'].tail(10).min()
    recent_high = df['最高'].tail(10).max()
    ma5 = df_ma['MA5'].iloc[-1] if 'MA5' in df_ma.columns else current_price

    if current_price <= recent_low * 1.03:
        buy_price = current_price
        buy_type = '接近支撑位买入'
    elif current_price > ma5 * 1.02:
        buy_price = round(ma5, 2)
        buy_type = f'建议回调至MA5({round(ma5,2)})买入'
    else:
        buy_price = current_price
        buy_type = '收盘价买入'

    take_profit = round(buy_price * 1.10, 2)
    stop_loss = round(buy_price * 0.95, 2)

    return {
        'buy_price': round(buy_price, 2),
        'buy_type': buy_type,
        'take_profit_price': take_profit,
        'stop_loss_price': stop_loss,
        'support_level': round(recent_low, 2),
        'resistance_level': round(recent_high, 2),
    }


def run_screening(conn, top_n=10):
    """执行选股主流程"""
    print(f"[{datetime.now()}] 开始选股...")

    # 获取规则和政策关键词
    rules = get_active_rules(conn)
    policy_keywords = get_policy_keywords(conn)
    print(f"  活跃规则: {len(rules)} 条, 政策关键词: {len(policy_keywords)} 个")

    # 获取全A股实时行情
    print("  获取全A股实时行情...")
    try:
        stock_df = ak.stock_zh_a_spot_em()
    except Exception as e:
        print(f"  获取行情失败: {e}")
        return []

    # 预过滤
    stock_df = stock_df[stock_df['代码'].str.match(r'^(60|00|30)')]
    stock_df = stock_df[~stock_df['名称'].str.contains('ST', na=False)]
    stock_df = stock_df[stock_df['成交量'] > 0]
    stock_df = stock_df[stock_df['最新价'] > 2]
    stock_df = stock_df[stock_df['最新价'] < 200]
    # 取成交额前 300 只
    stock_df = stock_df.sort_values('成交额', ascending=False).head(300)
    print(f"  候选股: {len(stock_df)} 只")

    # 获取资金流向
    print("  获取资金流向...")
    fund_flow_df = pd.DataFrame()
    try:
        fund_flow_df = ak.stock_individual_fund_flow_rank(indicator="今日")
        time.sleep(1)
    except Exception:
        print("  资金流向获取失败，跳过")

    # 逐只打分
    candidates = []
    total = len(stock_df)
    for idx, (_, row) in enumerate(stock_df.iterrows()):
        code = str(row['代码'])
        name = str(row['名称'])
        price = float(row['最新价'])
        pe = row.get('市盈率-动态')
        sector = str(row.get('板块', ''))

        if (idx + 1) % 50 == 0:
            print(f"  进度: {idx+1}/{total}")

        # 获取K线
        try:
            kline = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if kline is None or kline.empty or len(kline) < 25:
                continue
            kline = kline.tail(60)
            time.sleep(0.3)
        except Exception:
            continue

        # 各规则打分
        rule_scores = {}
        total_score = 0

        for rule in rules:
            rule_name = rule['name']
            weight = float(rule['weight'])
            score = 0

            if rule_name == 'MA5上穿MA20':
                score = score_ma_cross(kline)
            elif rule_name == 'MACD金叉':
                score = score_macd_cross(kline)
            elif rule_name == '放量突破':
                score = score_volume_breakout(kline)
            elif rule_name == 'PE合理':
                score = score_pe(pe)
            elif rule_name == '主力净流入':
                net = 0
                if not fund_flow_df.empty:
                    fr = fund_flow_df[fund_flow_df['代码'] == code]
                    if not fr.empty:
                        net = fr.iloc[0].get('主力净流入-净额', 0)
                score = score_fund_flow(net)
            elif rule_name == '政策利好板块':
                score = score_policy_related(sector, policy_keywords)

            weighted = score * weight
            rule_scores[rule_name] = {'score': score, 'weighted': round(weighted, 2)}
            total_score += weighted

        if total_score > 50:
            buy_signal = generate_buy_signal(price, kline)
            reasons = [f"{k}({v['score']}分)" for k, v in rule_scores.items() if v['score'] > 50]
            candidates.append({
                'code': code,
                'name': name,
                'sector': sector,
                'price': price,
                'score': round(total_score, 2),
                'rule_scores': rule_scores,
                'reasons': reasons,
                'buy_signal': buy_signal,
            })

    # 排序取 Top N
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_stocks = candidates[:top_n]
    print(f"\n  选出 {len(top_stocks)} 只推荐股票")
    return top_stocks


def save_recommendations(conn, stocks):
    """保存选股结果到数据库"""
    today = date.today()
    with conn.cursor() as cursor:
        # 先删除今天已有的推荐（避免重复）
        cursor.execute("DELETE FROM stock_recommendation WHERE recommend_date = %s", (today,))

        sql = """INSERT INTO stock_recommendation
                 (stock_code, stock_name, sector, total_score, reason, rule_scores,
                  recommend_date, recommend_price, buy_price, buy_type,
                  take_profit_price, stop_loss_price, support_level, resistance_level, max_hold_days)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

        for s in stocks:
            bs = s['buy_signal']
            reason_text = '、'.join(s['reasons']) if s['reasons'] else '综合评分较高'
            cursor.execute(sql, (
                s['code'], s['name'], s['sector'], s['score'],
                reason_text, json.dumps(s['rule_scores'], ensure_ascii=False),
                today, s['price'],
                bs['buy_price'], bs['buy_type'],
                bs['take_profit_price'], bs['stop_loss_price'],
                bs.get('support_level'), bs.get('resistance_level'), 10
            ))
    conn.commit()
    print(f"  已保存 {len(stocks)} 条推荐到数据库")


def main():
    parser = argparse.ArgumentParser(description='本地每日选股，结果写入远程MySQL')
    parser.add_argument('--host', default='81.69.42.239', help='MySQL主机')
    parser.add_argument('--port', type=int, default=3306, help='MySQL端口')
    parser.add_argument('--user', default='root', help='MySQL用户名')
    parser.add_argument('--password', default='root123', help='MySQL密码')
    parser.add_argument('--database', default='ai_stock', help='数据库名')
    parser.add_argument('--top', type=int, default=10, help='推荐数量')
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  AI 股票助手 - 每日选股")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    conn = get_connection(args.host, args.port, args.user, args.password, args.database)

    stocks = run_screening(conn, top_n=args.top)

    if stocks:
        save_recommendations(conn, stocks)
        print(f"\n{'='*60}")
        print("  今日推荐：")
        print(f"{'='*60}")
        for i, s in enumerate(stocks):
            print(f"  {i+1}. {s['name']}({s['code']}) "
                  f"板块:{s['sector']} 评分:{s['score']} "
                  f"买入价:{s['buy_signal']['buy_price']} "
                  f"止盈:{s['buy_signal']['take_profit_price']} "
                  f"止损:{s['buy_signal']['stop_loss_price']}")
        print(f"{'='*60}")
    else:
        print("\n  今日无符合条件的推荐")

    conn.close()


if __name__ == '__main__':
    main()
