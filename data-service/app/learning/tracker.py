"""推荐跟踪模块

记录每只推荐股在 T+1/3/5/10 的表现，计算涨跌幅。
"""
from datetime import date, datetime, timedelta
from app.db import get_connection
from app.stock_data.market_data import get_daily_kline


TRACK_DAYS = [1, 3, 5, 10]


def track_recommendations():
    """跟踪所有未完成跟踪的推荐

    每日 16:00 执行，检查哪些推荐已经到了跟踪时间点。
    """
    print(f"[{datetime.now()}] 开始跟踪推荐表现...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取所有需要跟踪的推荐（最近 15 天内的推荐）
            sql = """SELECT r.id, r.stock_code, r.stock_name, r.recommend_date, r.recommend_price
                     FROM stock_recommendation r
                     WHERE r.recommend_date >= DATE_SUB(CURDATE(), INTERVAL 15 DAY)"""
            cursor.execute(sql)
            recommendations = cursor.fetchall()
    finally:
        conn.close()

    tracked_count = 0
    today = date.today()

    for rec in recommendations:
        rec_date = rec['recommend_date']
        if isinstance(rec_date, str):
            rec_date = datetime.strptime(rec_date, '%Y-%m-%d').date()

        stock_code = rec['stock_code']
        recommend_price = float(rec['recommend_price']) if rec['recommend_price'] else 0

        if recommend_price <= 0:
            continue

        for days in TRACK_DAYS:
            target_date = rec_date + timedelta(days=days)

            # 还没到跟踪日期
            if target_date > today:
                continue

            # 检查是否已跟踪过
            if is_already_tracked(rec['id'], days):
                continue

            # 获取目标日期的收盘价
            close_price = get_close_price_on_date(stock_code, target_date)
            if close_price is None:
                continue

            # 计算涨跌幅
            change_pct = round((close_price - recommend_price) / recommend_price * 100, 2)

            # 保存跟踪记录
            save_tracking(rec['id'], days, close_price, change_pct, target_date)
            tracked_count += 1

    print(f"[{datetime.now()}] 跟踪完成，新增 {tracked_count} 条记录")


def is_already_tracked(recommendation_id, days_after):
    """检查是否已有跟踪记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT COUNT(*) as cnt FROM recommendation_tracking
                     WHERE recommendation_id = %s AND days_after = %s"""
            cursor.execute(sql, (recommendation_id, days_after))
            result = cursor.fetchone()
            return result['cnt'] > 0
    finally:
        conn.close()


def get_close_price_on_date(stock_code, target_date):
    """获取指定日期的收盘价"""
    try:
        kline = get_daily_kline(stock_code, days=15)
        if kline.empty:
            return None

        # 找到目标日期或最近的交易日
        target_str = target_date.strftime('%Y-%m-%d')
        if '日期' in kline.columns:
            kline['日期'] = kline['日期'].astype(str)
            row = kline[kline['日期'] == target_str]
            if not row.empty:
                return float(row.iloc[0]['收盘'])
            # 如果目标日期非交易日，取之前最近的交易日
            kline_before = kline[kline['日期'] <= target_str]
            if not kline_before.empty:
                return float(kline_before.iloc[-1]['收盘'])
    except Exception as e:
        print(f"获取 {stock_code} 在 {target_date} 的收盘价失败: {e}")
    return None


def save_tracking(recommendation_id, days_after, close_price, change_pct, tracked_at):
    """保存跟踪记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT INTO recommendation_tracking
                     (recommendation_id, days_after, close_price, change_pct, tracked_at)
                     VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(sql, (recommendation_id, days_after, close_price, change_pct, tracked_at))
        conn.commit()
    finally:
        conn.close()


def get_performance_summary():
    """获取推荐表现统计"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 整体胜率（T+5 涨幅 > 0 为盈利）
            sql = """SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as win_count,
                        AVG(change_pct) as avg_change,
                        MAX(change_pct) as max_change,
                        MIN(change_pct) as min_change
                     FROM recommendation_tracking
                     WHERE days_after = 5"""
            cursor.execute(sql)
            t5_stats = cursor.fetchone()

            # 各 T+N 平均收益
            sql2 = """SELECT days_after,
                        COUNT(*) as total,
                        AVG(change_pct) as avg_change,
                        SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as win_count
                      FROM recommendation_tracking
                      GROUP BY days_after
                      ORDER BY days_after"""
            cursor.execute(sql2)
            by_days = cursor.fetchall()

            return {
                "t5_stats": t5_stats,
                "by_days": by_days,
                "overall_win_rate": round(
                    t5_stats['win_count'] / t5_stats['total'] * 100, 2
                ) if t5_stats and t5_stats['total'] > 0 else 0
            }
    finally:
        conn.close()
