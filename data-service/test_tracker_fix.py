#!/usr/bin/env python3
# 测试tracker修复
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("测试每日选股跟踪功能修复")
print("=" * 60)

try:
    # 测试1: 测试单个股票的K线获取
    print("\n1. 测试K线数据获取...")
    from app.stock_data.market_data import get_daily_kline
    
    test_codes = ['601658', '601601', '600332']  # 使用错误日志中的股票代码
    
    for code in test_codes:
        print(f"\n  测试股票 {code}:")
        try:
            kline = get_daily_kline(code, days=10)
            if not kline.empty:
                print(f"    ✓ 成功获取K线数据，共{len(kline)}条记录")
                if '日期' in kline.columns and '收盘' in kline.columns:
                    print(f"    最近交易日: {kline.iloc[0]['日期']}, 收盘价: {kline.iloc[0]['收盘']}")
                elif '日期' in kline.columns and '收盘价' in kline.columns:
                    print(f"    最近交易日: {kline.iloc[0]['日期']}, 收盘价: {kline.iloc[0]['收盘价']}")
            else:
                print(f"    ✗ 获取到空数据")
        except Exception as e:
            print(f"    ✗ 获取失败: {e}")
    
    # 测试2: 测试tracker的核心功能
    print("\n2. 测试tracker核心功能...")
    from app.learning.tracker import get_close_price_on_date
    from datetime import date, timedelta
    
    test_date = date.today() - timedelta(days=5)  # 5天前
    
    for code in test_codes[:2]:  # 只测试前2个
        print(f"\n  测试股票 {code} 在 {test_date} 的收盘价:")
        try:
            close_price = get_close_price_on_date(code, test_date)
            if close_price:
                print(f"    ✓ 收盘价: {close_price}")
            else:
                print(f"    ✗ 无法获取收盘价")
        except Exception as e:
            print(f"    ✗ 获取失败: {e}")
    
    # 测试3: 测试数据库连接
    print("\n3. 测试数据库连接...")
    from app.db import get_connection
    try:
        conn = get_connection()
        conn.close()
        print("    ✓ 数据库连接正常")
    except Exception as e:
        print(f"    ✗ 数据库连接失败: {e}")
    
    print("\n" + "=" * 60)
    print("修复总结:")
    print("1. 增加了多方案降级获取K线数据")
    print("   - 主方案: akshare库")
    print("   - 降级方案1: 直接调用东方财富API")
    print("   - 降级方案2: 本地数据库缓存")
    print("2. 增加了错误处理和重试机制")
    print("3. 优化了tracker的健壮性，单个股票失败不影响整体")
    print("\n注意事项:")
    print("1. 东方财富API可能有频率限制，增加了请求间隔")
    print("2. 如果所有方案都失败，会记录日志并跳过该股票")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()