"""选股引擎 — 腾讯接口版

每日盘后运行，使用腾讯财经接口获取行情和K线，多维度打分，输出 Top N 推荐。
不依赖 AkShare，避免网络限制问题。
"""
import time
import json
import random
import requests
import pandas as pd
from datetime import date, datetime
from app.db import get_connection
from app.stock_data.stock_pool import STOCK_POOL


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def code_to_tencent(code):
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'


def fetch_kline_tencent(stock_code, days=60):
    """从腾讯接口获取最近 N 天K线"""
    tc_code = code_to_tencent(stock_code)
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,,,{days},qfq"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        stock_data = data.get('data', {}).get(tc_code, {})
        klines = stock_data.get('qfqday', stock_data.get('day', []))
        if not klines:
            return None
        rows = []
        for k in klines:
            if len(k) >= 6:
                rows.append({
                    '日期': k[0],
                    '开盘': float(k[1]),
                    '收盘': float(k[2]),
                    '最高': float(k[3]),
                    '最低': float(k[4]),
                    '成交量': int(float(k[5])),
                })
        return pd.DataFrame(rows) if rows else None
    except Exception:
        return None


def fetch_realtime_batch(stock_codes):
    """批量获取实时行情"""
    results = {}
    for i in range(0, len(stock_codes), 50):
        batch = stock_codes[i:i+50]
        codes_str = ','.join([code_to_tencent(c) for c in batch])
        url = f"http://qt.gtimg.cn/q={codes_str}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'gbk'
            for line in resp.text.strip().split('\n'):
                if '~' not in line:
                    continue
                parts = line.split('~')
                if len(parts) < 45:
                    continue
                code = parts[2]
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                volume = int(float(parts[6])) if parts[6] else 0
                change_pct = float(parts[32]) if parts[32] else 0
                pe = float(parts[39]) if parts[39] else 0
                if price > 0:
                    results[code] = {
                        'name': name, 'price': price,
                        'volume': volume * 100, 'change_pct': change_pct, 'pe': pe,
                    }
        except Exception:
            pass
        time.sleep(0.5)
    return results


def calculate_ma(df):
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    return df


def calculate_macd(df):
    ema12 = df['收盘'].ewm(span=12).mean()
    ema26 = df['收盘'].ewm(span=26).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9).mean()
    return df


def score_ma_cross(df):
    if len(df) < 21:
        return 0
    df = calculate_ma(df.copy())
    ma5_t = df['MA5'].iloc[-1]
    ma5_y = df['MA5'].iloc[-2]
    ma20_t = df['MA20'].iloc[-1]
    ma20_y = df['MA20'].iloc[-2]
    if pd.isna(ma5_t) or pd.isna(ma20_t):
        return 0
    if ma5_t > ma20_t and ma5_y <= ma20_y:
        return 85
    elif ma5_t > ma20_t:
        return 40
    return 0


def score_macd_cross(df):
    if len(df) < 30:
        return 0
    df = calculate_macd(df.copy())
    if pd.isna(df['DIF'].iloc[-1]):
        return 0
    if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] and df['DIF'].iloc[-2] <= df['DEA'].iloc[-2]:
        return 80
    return 0


def score_volume_breakout(df):
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


def score_pe(pe_value):
    if pe_value is None or pe_value <= 0:
        return 0
    if pe_value < 15:
        return 70
    elif pe_value < 25:
        return 50
    elif pe_value < 35:
        return 30
    return 0


def score_policy_related(stock_name, policy_keywords):
    if not stock_name or not policy_keywords:
        return 0
    match = sum(1 for kw in policy_keywords if kw in stock_name)
    if match >= 2:
        return 90
    elif match == 1:
        return 70
    return 0


def generate_buy_signal(price, df):
    if df is None or df.empty or len(df) < 20:
        return {
            'buy_price': price, 'buy_type': '收盘价买入',
            'take_profit_price': round(price * 1.10, 2),
            'stop_loss_price': round(price * 0.95, 2),
            'support_level': None, 'resistance_level': None,
        }
    df_ma = calculate_ma(df.copy())
    recent_low = df['最低'].tail(10).min()
    recent_high = df['最高'].tail(10).max()
    ma5 = df_ma['MA5'].iloc[-1]
    if pd.isna(ma5):
        ma5 = price
    if price <= recent_low * 1.03:
        buy_price, buy_type = price, '接近支撑位买入'
    elif price > ma5 * 1.02:
        buy_price, buy_type = round(ma5, 2), f'建议回调至MA5({round(ma5,2)})买入'
    else:
        buy_price, buy_type = price, '收盘价买入'
    return {
        'buy_price': round(buy_price, 2), 'buy_type': buy_type,
        'take_profit_price': round(buy_price * 1.10, 2),
        'stop_loss_price': round(buy_price * 0.95, 2),
        'support_level': round(recent_low, 2),
        'resistance_level': round(recent_high, 2),
    }


def get_active_rules():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM screening_rules WHERE status = 'active'")
            return cursor.fetchall()
    finally:
        conn.close()


def get_policy_keywords():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT keywords, related_sectors FROM policy_news
                             WHERE created_at > DATE_SUB(NOW(), INTERVAL 3 DAY)
                             AND keywords IS NOT NULL""")
            rows = cursor.fetchall()
            keywords = set()
            for row in rows:
                if row.get('keywords'):
                    for kw in row['keywords'].split(','):
                        if kw.strip():
                            keywords.add(kw.strip())
            return list(keywords)
    finally:
        conn.close()


def save_recommendation(stock_code, stock_name, sector, total_score, reason,
                        rule_scores, price, buy_signal=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT INTO stock_recommendation
                     (stock_code, stock_name, sector, total_score, reason, rule_scores,
                      recommend_date, recommend_price, buy_price, buy_type,
                      take_profit_price, stop_loss_price, support_level, resistance_level, max_hold_days)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (
                stock_code, stock_name, sector, total_score,
                reason, json.dumps(rule_scores, ensure_ascii=False),
                date.today(), price,
                buy_signal.get('buy_price') if buy_signal else price,
                buy_signal.get('buy_type', '收盘价买入') if buy_signal else '收盘价买入',
                buy_signal.get('take_profit_price') if buy_signal else round(price * 1.10, 2),
                buy_signal.get('stop_loss_price') if buy_signal else round(price * 0.95, 2),
                buy_signal.get('support_level') if buy_signal else None,
                buy_signal.get('resistance_level') if buy_signal else None,
                buy_signal.get('max_hold_days', 10) if buy_signal else 10,
            ))
        conn.commit()
    finally:
        conn.close()


def run_screening(top_n=10):
    """执行每日选股（腾讯接口版）"""
    print(f"[{datetime.now()}] 开始执行选股...")

    rules = get_active_rules()
    policy_keywords = get_policy_keywords()
    print(f"  活跃规则: {len(rules)} 条, 政策关键词: {len(policy_keywords)} 个")

    if not rules:
        print("  错误：没有活跃规则")
        return []

    # 获取实时行情
    print(f"  获取 {len(STOCK_POOL)} 只股票实时行情...")
    realtime = fetch_realtime_batch(STOCK_POOL)
    print(f"  获取到 {len(realtime)} 只有效行情")

    if not realtime:
        print("  获取股票列表失败，终止")
        return []

    # 过滤
    valid_codes = [c for c in STOCK_POOL if c in realtime
                   and realtime[c]['price'] > 2
                   and 'ST' not in realtime[c].get('name', '')]
    print(f"  预过滤后: {len(valid_codes)} 只候选股")

    # 打分
    candidates = []
    for i, code in enumerate(valid_codes):
        info = realtime[code]
        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{len(valid_codes)}")

        kline = fetch_kline_tencent(code, days=60)
        if kline is None or len(kline) < 20:
            time.sleep(0.3)
            continue

        rule_scores = {}
        total_score = 0
        for rule in rules:
            name = rule['name']
            weight = float(rule['weight'])
            score = 0
            if name == 'MA5上穿MA20':
                score = score_ma_cross(kline)
            elif name == 'MACD金叉':
                score = score_macd_cross(kline)
            elif name == '放量突破':
                score = score_volume_breakout(kline)
            elif name == 'PE合理':
                score = score_pe(info.get('pe'))
            elif name == '主力净流入':
                score = 50 if info.get('change_pct', 0) > 1 else 0
            elif name == '政策利好板块':
                score = score_policy_related(info.get('name', ''), policy_keywords)

            weighted = score * weight
            rule_scores[name] = {'score': score, 'weighted': round(weighted, 2)}
            total_score += weighted

        if total_score > 50:
            buy_signal = generate_buy_signal(info['price'], kline)
            reasons = [f"{k}({v['score']}分)" for k, v in rule_scores.items() if v['score'] > 50]
            candidates.append({
                'code': code, 'name': info['name'],
                'sector': '', 'price': info['price'],
                'score': round(total_score, 2),
                'rule_scores': rule_scores, 'reasons': reasons,
                'buy_signal': buy_signal,
            })
        time.sleep(0.3)

    # 排序取 Top N
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_stocks = candidates[:top_n]

    # 清除今天旧数据并保存
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM stock_recommendation WHERE recommend_date = CURDATE()")
        conn.commit()
    finally:
        conn.close()

    for stock in top_stocks:
        reason_text = '、'.join(stock['reasons']) if stock['reasons'] else '综合评分较高'
        save_recommendation(
            stock['code'], stock['name'], stock['sector'],
            stock['score'], reason_text, stock['rule_scores'],
            stock['price'], stock.get('buy_signal')
        )

    print(f"[{datetime.now()}] 选股完成，推荐 {len(top_stocks)} 只股票")
    return top_stocks


def get_today_recommendations():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM stock_recommendation
                             WHERE recommend_date = CURDATE()
                             ORDER BY total_score DESC""")
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('recommend_date'):
                    r['recommend_date'] = r['recommend_date'].strftime('%Y-%m-%d')
                if r.get('sell_date'):
                    r['sell_date'] = r['sell_date'].strftime('%Y-%m-%d')
            return results
    finally:
        conn.close()


def get_history_recommendations(date_str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM stock_recommendation
                             WHERE recommend_date = %s
                             ORDER BY total_score DESC""", (date_str,))
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('recommend_date'):
                    r['recommend_date'] = r['recommend_date'].strftime('%Y-%m-%d')
                if r.get('sell_date'):
                    r['sell_date'] = r['sell_date'].strftime('%Y-%m-%d')
            return results
    finally:
        conn.close()
