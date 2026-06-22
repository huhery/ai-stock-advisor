# -*- coding: utf-8 -*-
"""重置并重新计算卖出信号

由于此前 get_daily_kline 排序错误（最新在前 vs 在后），
导致卖出价取到了最旧的历史价，产生大量错误的卖出记录
（如帝尔激光120.27、大唐发电5.04，以及当天买当天卖）。

本脚本：
1. 清空所有错误的卖出字段（sell_price/sell_type/sell_date/profit_pct）
2. 用修复后的逻辑重新跑卖出信号检查

注意：这会重置全部卖出记录。买入价(buy_price)等推荐数据保留不动。
"""
import sys
sys.path.insert(0, '.')
from app.db import get_connection
from app.screening.signals import check_all_holdings


def reset_all_sell_fields():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_recommendation
                SET sell_price = NULL, sell_type = NULL,
                    sell_date = NULL, profit_pct = NULL
                WHERE sell_price IS NOT NULL
            """)
            affected = cursor.rowcount
        conn.commit()
        print(f"已重置 {affected} 条错误卖出记录")
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 50)
    print("步骤1: 重置所有卖出字段")
    reset_all_sell_fields()

    print("\n步骤2: 用修复后的逻辑重新检查卖出信号")
    check_all_holdings()

    print("\n完成。请刷新前端每日选股页面查看。")
