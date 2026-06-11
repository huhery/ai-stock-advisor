"""本地每日选股脚本 - 使用腾讯财经接口

不依赖 AkShare，全部使用腾讯财经 HTTP 接口获取数据。
选股结果写入远程 MySQL。

使用方法：
    pip install requests pymysql cryptography
    python scripts/daily_screening_local.py --host 81.69.42.239 --password AiStock2026!
"""
import time
import json
import argparse
import pymysql
import requests
import pandas as pd
from datetime import date, datetime
from app.stock_data.stock_pool import STOCK_POOL


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def get_connection(host, port, user, password, database):
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


def code_to_tencent(code):
    """转为腾讯格式"""
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
        if not rows:
            return None
        df = pd.DataFrame(rows)
        return df
    except Exception as e:
        return None


def fetch_realtime_tencent(stock_codes):
    """批量获取实时行情（腾讯接口，一次最多 50 只）

    返回 dict: {code: {price, name, volume, change_pct, pe, ...}}
    """
    results = {}
    # 分批，每批 50 只
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
                volume = int(float(parts[6])) if parts[6] else 0  # 成交量（手）
                change_pct = float(parts[32]) if parts[32] else 0
                pe = float(parts[39]) if parts[39] else 0

                if price > 0:
                    results[code] = {
                        'name': name,
                        'price': price,
                        'volume': volume * 100,  # 转为股
                        'change_pct': change_pct,
                        'pe': pe,
                    }
        except Exception:
            pass
        time.sleep(0.5)
    return results


def get_active_rules(conn):
    """获取活跃规则"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM screening_rules WHERE status = 'active'")
        return cursor.fetchall()


def get_policy_keywords(conn):
    """获取政策关键词"""
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
                    if kw.strip():
                        keywords.add(kw.strip())
        return list(keywords)


# ===== 打分规则 =====

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


def score_policy(sector, keywords):
    if not sector or not keywords:
        return 0
    match = sum(1 for kw in keywords if kw in sector)
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


def run_screening(conn, top_n=10):
    """执行选股"""
    print(f"[{datetime.now()}] 开始选股...\n")

    rules = get_active_rules(conn)
    policy_keywords = get_policy_keywords(conn)
    print(f"  活跃规则: {len(rules)} 条, 政策关键词: {len(policy_keywords)} 个")

    if not rules:
        print("  错误：没有活跃规则！请先运行 init_rules.py")
        return []

    # 获取实时行情
    print(f"  获取 {len(STOCK_POOL)} 只股票的实时行情...")
    realtime = fetch_realtime_tencent(STOCK_POOL)
    print(f"  获取到 {len(realtime)} 只有效行情")

    # 过滤：排除停牌和异常
    valid_codes = [c for c in STOCK_POOL if c in realtime and realtime[c]['price'] > 2
                   and 'ST' not in realtime[c].get('name', '')]
    print(f"  有效候选: {len(valid_codes)} 只\n")

    # 逐只获取K线并打分
    candidates = []
    for i, code in enumerate(valid_codes):
        info = realtime[code]
        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{len(valid_codes)}")

        kline = fetch_kline_tencent(code, days=60)
        if kline is None or len(kline) < 20:
            time.sleep(0.3)
            continue

        # 打分
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
                score = 50 if info.get('change_pct', 0) > 1 else 0  # 简化：涨幅>1%近似有主力
            elif name == '政策利好板块':
                score = score_policy(info.get('name', ''), policy_keywords)

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

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_stocks = candidates[:top_n]
    print(f"\n  选出 {len(top_stocks)} 只推荐股票")
    return top_stocks


def save_recommendations(conn, stocks, recommend_date=None):
    """保存到数据库"""
    if recommend_date is None:
        recommend_date = date.today().strftime('%Y-%m-%d')
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM stock_recommendation WHERE recommend_date = %s", (recommend_date,))
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
                recommend_date, s['price'],
                bs['buy_price'], bs['buy_type'],
                bs['take_profit_price'], bs['stop_loss_price'],
                bs.get('support_level'), bs.get('resistance_level'), 10
            ))
    conn.commit()
    print(f"  已保存 {len(stocks)} 条推荐到数据库（日期: {recommend_date}）")


def main():
    parser = argparse.ArgumentParser(description='每日选股（腾讯接口版）')
    parser.add_argument('--host', default='81.69.42.239')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', default='AiStock2026!')
    parser.add_argument('--database', default='ai_stock')
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--date', default=None, help='指定推荐日期，格式 YYYY-MM-DD（默认今天）')
    args = parser.parse_args()

    # 确定推荐日期
    recommend_date = args.date if args.date else date.today().strftime('%Y-%m-%d')

    print(f"{'='*60}")
    print(f"  AI 股票助手 - 每日选股（腾讯接口版）")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  推荐日期: {recommend_date}")
    print(f"{'='*60}\n")

    conn = get_connection(args.host, args.port, args.user, args.password, args.database)
    stocks = run_screening(conn, top_n=args.top)

    if stocks:
        save_recommendations(conn, stocks, recommend_date)
        print(f"\n{'='*60}")
        print(f"  {recommend_date} 推荐：")
        print(f"{'='*60}")
        for i, s in enumerate(stocks):
            print(f"  {i+1}. {s['name']}({s['code']}) "
                  f"评分:{s['score']} "
                  f"买入:{s['buy_signal']['buy_price']} "
                  f"止盈:{s['buy_signal']['take_profit_price']} "
                  f"止损:{s['buy_signal']['stop_loss_price']}")
    else:
        print("\n  今日无符合条件的推荐")

    conn.close()


if __name__ == '__main__':
    main()
