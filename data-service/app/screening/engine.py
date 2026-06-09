"""选股引擎

每日盘后运行，对全 A 股进行多维度打分，输出 Top N 推荐。
"""
from datetime import date, datetime
from app.db import get_connection
from app.stock_data.market_data import (
    get_stock_list, get_daily_kline, get_fund_flow_rank
)
from app.screening.rules import (
    rule_ma_cross, rule_macd_golden_cross, rule_volume_breakout,
    rule_pe_reasonable, rule_main_fund_inflow, rule_policy_related
)


def get_active_rules():
    """获取所有活跃的筛选规则及权重"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM screening_rules WHERE status = 'active'"
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


def get_policy_keywords():
    """从最近的政策资讯中提取关键词"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT keywords, related_sectors FROM policy_news
                     WHERE created_at > DATE_SUB(NOW(), INTERVAL 3 DAY)
                     AND keywords IS NOT NULL"""
            cursor.execute(sql)
            rows = cursor.fetchall()
            keywords = set()
            for row in rows:
                if row.get('keywords'):
                    for kw in row['keywords'].split(','):
                        kw = kw.strip()
                        if kw:
                            keywords.add(kw)
                if row.get('related_sectors'):
                    for s in row['related_sectors'].split(','):
                        s = s.strip()
                        if s:
                            keywords.add(s)
            return list(keywords)
    finally:
        conn.close()


def score_stock(stock_row, kline_df, fund_flow_df, policy_keywords, rules):
    """对单只股票进行综合打分

    Args:
        stock_row: 股票实时行情数据行
        kline_df: 日K线 DataFrame
        fund_flow_df: 资金流向数据
        policy_keywords: 政策关键词列表
        rules: 活跃规则列表

    Returns:
        (total_score, rule_scores_dict, reasons_list)
    """
    rule_scores = {}
    total_score = 0
    reasons = []

    stock_code = str(stock_row.get('代码', ''))
    stock_name = str(stock_row.get('名称', ''))
    pe_value = stock_row.get('市盈率-动态')
    sector = str(stock_row.get('板块', ''))

    for rule in rules:
        rule_name = rule['name']
        weight = float(rule['weight'])
        score = 0

        if rule_name == 'MA5上穿MA20':
            score = rule_ma_cross(kline_df)
        elif rule_name == 'MACD金叉':
            score = rule_macd_golden_cross(kline_df)
        elif rule_name == '放量突破':
            score = rule_volume_breakout(kline_df)
        elif rule_name == 'PE合理':
            score = rule_pe_reasonable(pe_value)
        elif rule_name == '主力净流入':
            # 从资金流向表查找
            net_inflow = 0
            if not fund_flow_df.empty:
                fund_row = fund_flow_df[fund_flow_df['代码'] == stock_code]
                if not fund_row.empty:
                    net_inflow = fund_row.iloc[0].get('主力净流入-净额', 0)
            score = rule_main_fund_inflow(net_inflow)
        elif rule_name == '政策利好板块':
            score = rule_policy_related(sector, policy_keywords)

        weighted_score = score * weight
        rule_scores[rule_name] = {'score': score, 'weighted': round(weighted_score, 2)}
        total_score += weighted_score

        if score > 50:
            reasons.append(f"{rule_name}({score}分)")

    return round(total_score, 2), rule_scores, reasons


def save_recommendation(stock_code, stock_name, sector, total_score, reason, rule_scores, price, buy_signal=None):
    """保存选股结果到数据库（含买卖点）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT INTO stock_recommendation
                     (stock_code, stock_name, sector, total_score, reason, rule_scores,
                      recommend_date, recommend_price, buy_price, buy_type,
                      take_profit_price, stop_loss_price, support_level, resistance_level, max_hold_days)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            import json
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
    """执行每日选股

    流程：
    1. 获取活跃规则和权重
    2. 获取全 A 股实时行情
    3. 预过滤（排除 ST、停牌、新股等）
    4. 对候选股打分
    5. 取 Top N 保存
    """
    print(f"[{datetime.now()}] 开始执行选股...")

    # 1. 获取规则和政策关键词
    rules = get_active_rules()
    policy_keywords = get_policy_keywords()
    print(f"  活跃规则: {len(rules)} 条, 政策关键词: {len(policy_keywords)} 个")

    # 2. 获取股票列表
    stock_df = get_stock_list()
    if stock_df.empty:
        print("  获取股票列表失败，终止")
        return

    # 3. 预过滤
    # 只保留沪深主板（60/00开头）和创业板（30开头）
    stock_df = stock_df[stock_df['代码'].str.match(r'^(60|00|30)')]
    # 排除 ST、*ST
    stock_df = stock_df[~stock_df['名称'].str.contains('ST', na=False)]
    # 排除停牌（成交量为0）
    stock_df = stock_df[stock_df['成交量'] > 0]
    # 排除价格异常
    stock_df = stock_df[stock_df['最新价'] > 2]
    stock_df = stock_df[stock_df['最新价'] < 200]

    print(f"  预过滤后: {len(stock_df)} 只候选股")

    # 4. 获取资金流向数据
    fund_flow_df = get_fund_flow_rank()

    # 5. 打分（为了效率，先用资金流筛选一轮）
    candidates = []
    # 限制扫描数量（全 A 扫描太慢，取成交活跃的前 500 只）
    stock_df_sorted = stock_df.sort_values('成交额', ascending=False).head(500)

    for idx, row in stock_df_sorted.iterrows():
        stock_code = str(row['代码'])
        try:
            kline_df = get_daily_kline(stock_code, days=30)
            if kline_df.empty:
                continue

            total_score, rule_scores, reasons = score_stock(
                row, kline_df, fund_flow_df, policy_keywords, rules
            )

            if total_score > 50:  # 最低分门槛
                # 生成买卖点信号
                from app.screening.signals import generate_buy_signal
                current_price = float(row.get('最新价', 0))
                buy_signal = generate_buy_signal(stock_code, current_price, kline_df)

                candidates.append({
                    'code': stock_code,
                    'name': row.get('名称', ''),
                    'sector': row.get('板块', '未知'),
                    'price': current_price,
                    'score': total_score,
                    'rule_scores': rule_scores,
                    'reasons': reasons,
                    'buy_signal': buy_signal
                })
        except Exception as e:
            continue

    # 6. 排序取 Top N
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top_stocks = candidates[:top_n]

    # 7. 保存结果
    for stock in top_stocks:
        reason_text = '、'.join(stock['reasons']) if stock['reasons'] else '综合评分较高'
        save_recommendation(
            stock['code'], stock['name'], stock['sector'],
            stock['score'], reason_text, stock['rule_scores'], stock['price'],
            stock.get('buy_signal')
        )

    print(f"[{datetime.now()}] 选股完成，推荐 {len(top_stocks)} 只股票")
    return top_stocks


def get_today_recommendations():
    """获取今日选股结果"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT * FROM stock_recommendation
                     WHERE recommend_date = CURDATE()
                     ORDER BY total_score DESC"""
            cursor.execute(sql)
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('recommend_date'):
                    r['recommend_date'] = r['recommend_date'].strftime('%Y-%m-%d')
            return results
    finally:
        conn.close()


def get_history_recommendations(date_str):
    """获取历史选股结果"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT * FROM stock_recommendation
                     WHERE recommend_date = %s
                     ORDER BY total_score DESC"""
            cursor.execute(sql, (date_str,))
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('recommend_date'):
                    r['recommend_date'] = r['recommend_date'].strftime('%Y-%m-%d')
            return results
    finally:
        conn.close()
