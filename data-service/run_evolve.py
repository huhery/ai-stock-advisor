#!/usr/bin/env python
"""微淼财务自由模块 — 手动进化脚本

不依赖 FastAPI 服务运行，直接在命令行执行即可。
分析最新政策、当前行情，自动调整筛选参数和投资建议。

用法：
    python run_evolve.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.weimu.evolution import run_weimu_evolution, get_latest_advice


def main():
    print("=" * 60)
    print("  微淼财务自由 — 手动进化")
    print("  分析政策 + 行情 → 更新规则 + 生成建议")
    print("=" * 60)
    print()

    run_weimu_evolution()

    print()
    print("=" * 60)
    print("  最新投资建议")
    print("=" * 60)
    advice = get_latest_advice()
    if advice:
        print()
        if advice.get('investment_notes'):
            print("  📌 投资注意事项：")
            for note in advice['investment_notes']:
                print(f"     • {note}")
        print()
        if advice.get('risk_warnings'):
            print("  ⚠️  风险警示：")
            for w in advice['risk_warnings']:
                print(f"     • {w}")
        print()
        if advice.get('allocation_advice'):
            print(f"  💰 配置方向：{advice['allocation_advice']}")
        print()
        if advice.get('updated_at'):
            print(f"  更新时间：{advice['updated_at']}")


if __name__ == '__main__':
    main()
