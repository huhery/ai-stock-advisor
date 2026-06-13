"""选股引擎 — 腾讯接口版

每日盘后运行，使用腾讯财经接口获取行情和K线，多维度打分，输出 Top N 推荐。
集成 Kronos AI 价格预测模型辅助打分。
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
from app.stock_data.sector_map import get_sector_with_fallback, get_sectors_batch


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
    """获取近期新闻的关键词和板块信息（国内+国际）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT keywords, related_sectors FROM policy_news
                             WHERE created_at > DATE_SUB(NOW(), INTERVAL 3 DAY)
                             AND (keywords IS NOT NULL OR related_sectors IS NOT NULL)""")
            rows = cursor.fetchall()
            keywords = set()
            for row in rows:
                if row.get('keywords'):
                    for kw in row['keywords'].split(','):
                        if kw.strip():
                            keywords.add(kw.strip())
                if row.get('related_sectors'):
                    for sector in row['related_sectors'].split(','):
                        if sector.strip():
                            keywords.add(sector.strip())
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


def _apply_kronos_prediction(candidates, kline_cache):
    """对候选股执行 Kronos AI 预测，将预测得分加入总分

    只对规则打分通过的候选股进行预测（通常几十只到几百只），
    利用 GPU 批量推理，效率较高。
    """
    if not candidates:
        return candidates

    try:
        from app.prediction.kronos_predictor import predict_batch, score_prediction
    except ImportError:
        print("  [Kronos] 模块未安装，跳过 AI 预测")
        return candidates

    # 准备批量数据
    kline_list = []
    for c in candidates:
        code = c['code']
        if code in kline_cache:
            kline_list.append((code, kline_cache[code]))

    if not kline_list:
        return candidates

    print(f"  第三轮：Kronos AI 预测 {len(kline_list)} 只候选股...")
    predictions = predict_batch(kline_list, pred_days=5)
    print(f"  [Kronos] 成功预测 {len(predictions)} 只")

    # 将预测得分融合到总分（权重 1.5）
    kronos_weight = 1.5
    for c in candidates:
        code = c['code']
        pred = predictions.get(code)
        if pred:
            pred_score = score_prediction(pred)
            weighted = pred_score * kronos_weight
            c['rule_scores']['AI价格预测'] = {
                'score': pred_score,
                'weighted': round(weighted, 2),
                'detail': pred
            }
            c['score'] = round(c['score'] + weighted, 2)
            if pred_score > 50:
                c['reasons'].append(f"AI价格预测({pred_score}分,预测涨{pred['pred_change_pct']}%)")

    return candidates


def run_screening(top_n=10):
    """执行每日选股（腾讯接口版，全A股多轮筛选）

    筛选流程：
    第一轮（批量行情，秒级）：基础过滤，排除垃圾股
    第二轮（批量行情，秒级）：量价初筛，保留有活力的股票
    第三轮（逐个K线，分钟级）：技术面精细打分
    第四轮（Kronos AI）：价格预测加分
    """
    print(f"[{datetime.now()}] 开始执行选股...")

    rules = get_active_rules()
    policy_keywords = get_policy_keywords()
    print(f"  活跃规则: {len(rules)} 条, 政策关键词: {len(policy_keywords)} 个")

    if not rules:
        print("  错误：没有活跃规则")
        return []

    # ========== 第一轮：批量获取实时行情 ==========
    stock_pool = list(STOCK_POOL)
    print(f"  股票池: {len(stock_pool)} 只股票")
    print(f"  第一轮：批量获取实时行情...")
    realtime = fetch_realtime_batch(stock_pool)
    print(f"  获取到 {len(realtime)} 只有效行情")

    if not realtime:
        print("  获取股票列表失败，终止")
        return []

    # ========== 第二轮：量价快速过滤（不需要K线，纯用实时数据） ==========
    print(f"  第二轮：量价快速过滤...")
    quick_filtered = []
    for code in stock_pool:
        if code not in realtime:
            continue
        info = realtime[code]
        price = info['price']
        name = info.get('name', '')
        change_pct = info.get('change_pct', 0)
        volume = info.get('volume', 0)
        pe = info.get('pe', 0)

        # 基础排除
        if price < 3 or price > 300:
            continue  # 排除低价股和高价股（高价股资金效率低）
        if 'ST' in name.upper():
            continue
        # 排除涨停（买不进）和跌停（可能有利空）
        if change_pct > 9.5 or change_pct < -9.5:
            continue
        # 排除成交量过低（日成交额 < 5000万，流动性差）
        # volume是手数，粗估成交额 = volume * price
        est_amount = volume * price
        if est_amount < 50000000:  # 5000万
            continue
        # 排除PE异常（亏损或PE>200的泡沫股）
        if pe < 0 or pe > 200:
            continue
        # 保留当日有正向表现或温和回调的（排除大跌>5%的）
        if change_pct < -5:
            continue

        quick_filtered.append(code)

    print(f"  第二轮过滤后: {len(quick_filtered)} 只（排除了 {len(realtime) - len(quick_filtered)} 只）")

    # ========== 第二轮半：涨幅/活跃度排序，取前200名 ==========
    # 按"活跃度得分"排序：涨幅适中+成交活跃的优先
    def activity_score(code):
        info = realtime[code]
        change = info.get('change_pct', 0)
        vol = info.get('volume', 0) * info['price']  # 估算成交额
        # 涨幅1-5%最佳，成交额越大越好
        change_score = 0
        if 1 <= change <= 5:
            change_score = 30
        elif 0 <= change < 1:
            change_score = 15
        elif 5 < change <= 9:
            change_score = 20
        elif -3 <= change < 0:
            change_score = 10
        # 成交额打分
        vol_score = min(vol / 100000000, 30)  # 每亿元加分，上限30
        return change_score + vol_score

    quick_filtered.sort(key=activity_score, reverse=True)
    # 取前200只进入精细打分（大幅减少K线请求量）
    max_candidates = 200
    candidates_for_kline = quick_filtered[:max_candidates]
    print(f"  活跃度排序后取前 {len(candidates_for_kline)} 只进入精细打分")

    # 批量获取板块信息
    sector_map = get_sectors_batch(candidates_for_kline)

    # ========== 第三轮：逐个拉取K线精细打分 ==========
    print(f"  第三轮：K线技术面精细打分（{len(candidates_for_kline)}只）...")

    candidates = []
    kline_cache = {}
    for i, code in enumerate(candidates_for_kline):
        info = realtime[code]
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(candidates_for_kline)}")

        kline = fetch_kline_tencent(code, days=60)
        if kline is None or len(kline) < 20:
            time.sleep(0.2)
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
            kline_cache[code] = kline  # 缓存用于 Kronos
            candidates.append({
                'code': code, 'name': info['name'],
                'sector': sector_map.get(code, ''), 'price': info['price'],
                'score': round(total_score, 2),
                'rule_scores': rule_scores, 'reasons': reasons,
                'buy_signal': buy_signal,
            })
        time.sleep(0.2)

    print(f"  第三轮完成: {len(candidates)} 只通过技术面打分")

    # ========== 第四轮：Kronos AI 预测加分 ==========
    candidates = _apply_kronos_prediction(candidates, kline_cache)

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


def get_available_dates():
    """获取所有有选股记录的日期列表（降序）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT DISTINCT recommend_date
                             FROM stock_recommendation
                             ORDER BY recommend_date DESC
                             LIMIT 30""")
            results = cursor.fetchall()
            return [r['recommend_date'].strftime('%Y-%m-%d') for r in results if r.get('recommend_date')]
    finally:
        conn.close()
