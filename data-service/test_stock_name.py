#!/usr/bin/env python3
# 测试股票名称获取功能
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("测试股票名称获取功能")
print("=" * 60)

# 测试几个股票代码
test_codes = ['600519', '000858', '002304', '601658', '601601']

try:
    from app.weimu.screener import _get_stock_name
    
    for code in test_codes:
        print(f"\n测试股票代码: {code}")
        try:
            stock_name = _get_stock_name(code)
            print(f"  股票名称: {stock_name}")
        except Exception as e:
            print(f"  获取失败: {e}")
    
    # 测试数据库查询现有数据
    print("\n\n测试数据库中的现有数据:")
    print("=" * 40)
    
    from app.db import get_connection
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取最新一天的选股结果
            cursor.execute("""
                SELECT stock_code, stock_name, COUNT(*) as count 
                FROM weimu_recommendation 
                WHERE recommend_date = (
                    SELECT MAX(recommend_date) FROM weimu_recommendation
                )
                GROUP BY stock_code, stock_name
                LIMIT 10
            """)
            results = cursor.fetchall()
            
            print(f"最新数据中共有 {len(results)} 只股票:")
            for r in results:
                code = r['stock_code']
                name = r['stock_name']
                if name is None or name.startswith('股票'):
                    print(f"  {code}: 缺少股票名称 (当前: {name})")
                else:
                    print(f"  {code}: {name}")
    
    finally:
        conn.close()
    
    print("\n" + "=" * 60)
    print("建议:")
    print("1. 运行新的筛选会自动获取股票名称")
    print("2. 可以创建脚本更新现有数据的股票名称")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()