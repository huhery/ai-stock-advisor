#!/usr/bin/env python
"""微淼财务自由选股 — 手动重跑脚本

用法：
    python run_weimu.py           # 完整筛选（全A股扫描，耗时较长）
    python run_weimu.py --quick   # 快速模式（仅对上次结果重算估值）

基于微淼商学院课程的价值投资方法论：
  1. 海选：连续5年 ROE>15% + 现金含量>80% + 毛利率>30%
  2. 精选：ROE>20% + 现金含量>100% + 毛利率>40% + 负债率<60% + 连续分红>5年
  3. 估值：市场PE<20 + 个股PE<15 + 股息率>国债收益率 → 买入信号
"""
import sys
import os

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.weimu.runner import run_full, run_quick


def main():
    quick = '--quick' in sys.argv

    print("=" * 60)
    print("  微淼财务自由选股")
    print(f"  模式: {'快速（重算估值）' if quick else '完整（全A股扫描）'}")
    print("=" * 60)
    print()

    if quick:
        results = run_quick()
    else:
        results = run_full()

    if results:
        print()
        print("=" * 60)
        print("  筛选结果摘要")
        print("=" * 60)

        # 按估值分组展示
        buy_list = [r for r in results if r.get('valuation') == 'buy']
        hold_list = [r for r in results if r.get('valuation') == 'hold']
        wait_list = [r for r in results if r.get('valuation') == 'wait']
        sell_list = [r for r in results if r.get('valuation') == 'sell']

        if buy_list:
            print(f"\n  【可买入】({len(buy_list)} 只)")
            for r in buy_list:
                code = r.get('code', r.get('stock_code', ''))
                print(f"    {code} | ROE={r.get('roe_avg')}% | 毛利率={r.get('gross_margin_avg')}% "
                      f"| PE={r.get('pe')} | 股息率={r.get('dividend_yield')}%")

        if hold_list:
            print(f"\n  【可持有】({len(hold_list)} 只)")
            for r in hold_list:
                code = r.get('code', r.get('stock_code', ''))
                print(f"    {code} | ROE={r.get('roe_avg')}% | PE={r.get('pe')}")

        if wait_list:
            print(f"\n  【等待好价格】({len(wait_list)} 只)")
            for r in wait_list:
                code = r.get('code', r.get('stock_code', ''))
                print(f"    {code} | ROE={r.get('roe_avg')}% | PE={r.get('pe')}")

        if sell_list:
            print(f"\n  【建议卖出】({len(sell_list)} 只)")
            for r in sell_list:
                code = r.get('code', r.get('stock_code', ''))
                print(f"    {code} | PE={r.get('pe')}")

        print()
        print(f"  总计: {len(results)} 只好公司")
    else:
        print("\n  未找到符合条件的股票")


if __name__ == '__main__':
    main()
