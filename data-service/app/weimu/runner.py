"""微淼选股手动运行入口

提供命令行脚本和 API 路由注册。

命令行用法：
    python -m app.weimu.runner           # 执行完整筛选
    python -m app.weimu.runner --quick   # 仅对上次结果重算估值
"""
import sys
import threading
from datetime import datetime
from app.weimu.screener import run_weimu_screening
from app.weimu.valuation import get_market_pe, get_bond_yield, judge_valuation
from app.db import get_connection


# 全局进度状态
_progress = {"status": "idle"}


def run_full():
    """执行完整筛选（同步，供脚本直接调用）"""
    global _progress
    _progress = {"status": "running", "stage": "init", "message": "启动中..."}

    def on_progress(stage, current, total, message):
        global _progress
        _progress = {
            "status": "running",
            "stage": stage,
            "current": current,
            "total": total,
            "message": message,
        }

    try:
        results = run_weimu_screening(callback=on_progress)
        _progress = {
            "status": "completed",
            "message": f"完成，共 {len(results)} 只精选股",
            "count": len(results),
            "buy_count": sum(1 for r in results if r.get('valuation') == 'buy'),
        }
        return results
    except Exception as e:
        _progress = {"status": "failed", "message": str(e)}
        raise


def run_quick():
    """仅对已有精选结果重算估值（快速模式）"""
    print(f"[{datetime.now()}] 快速模式：重算估值...")

    market_pe = get_market_pe()
    bond_yield = get_bond_yield()
    print(f"  深证A股PE: {market_pe}, 10年国债: {bond_yield}%")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取最近一次结果
            cursor.execute("""
                SELECT * FROM weimu_recommendation
                WHERE recommend_date = (
                    SELECT MAX(recommend_date) FROM weimu_recommendation
                )
            """)
            results = cursor.fetchall()

            if not results:
                print("  没有历史数据，请先执行完整筛选")
                return []

            updated = 0
            for row in results:
                stock_pe = float(row['pe']) if row.get('pe') else None
                dividend_yield = float(row['dividend_yield']) if row.get('dividend_yield') else None

                valuation = judge_valuation(
                    stock_pe=stock_pe,
                    market_pe=market_pe,
                    dividend_yield=dividend_yield,
                    bond_yield=bond_yield,
                )

                cursor.execute(
                    "UPDATE weimu_recommendation SET valuation = %s, market_pe = %s WHERE id = %s",
                    (valuation, market_pe, row['id'])
                )
                updated += 1

            conn.commit()
            print(f"  更新 {updated} 条记录的估值状态")

            buy_count = sum(1 for row in results
                          if judge_valuation(
                              float(row['pe']) if row.get('pe') else None,
                              market_pe,
                              float(row['dividend_yield']) if row.get('dividend_yield') else None,
                              bond_yield
                          ) == 'buy')
            print(f"  当前可买入: {buy_count} 只")
            return results
    finally:
        conn.close()


def run_async():
    """异步执行完整筛选（供 API 调用）"""
    global _progress
    if _progress.get('status') == 'running':
        return False, "已有任务在运行中"

    def task():
        run_full()

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    return True, "微淼选股已启动，后台运行中"


def get_progress():
    """获取当前进度"""
    return _progress


# ===== 命令行入口 =====
if __name__ == '__main__':
    quick = '--quick' in sys.argv

    if quick:
        run_quick()
    else:
        run_full()
