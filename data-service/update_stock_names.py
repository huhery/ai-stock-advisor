#!/usr/bin/env python3
"""
更新现有微淼选股结果的股票名称

这个脚本会：
1. 查询所有缺少股票名称的记录
2. 获取每个股票的实时名称
3. 更新数据库中的股票名称
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import get_connection
import akshare as ak
import requests

def get_stock_name_from_akshare(stock_code):
    """使用akshare获取股票名称"""
    try:
        stock_spot = ak.stock_zh_a_spot_em()
        if not stock_spot.empty:
            matched = stock_spot[stock_spot['代码'] == stock_code]
            if not matched.empty:
                return matched.iloc[0]['名称']
    except Exception as e:
        print(f"  akshare获取 {stock_code} 名称失败: {e}")
    return None

def get_stock_name_from_eastmoney(stock_code):
    """使用东方财富API获取股票名称"""
    try:
        time.sleep(0.5)  # 避免请求过快
        
        # 根据股票代码确定市场前缀
        if stock_code.startswith('6'):
            secid = f"1.{stock_code}"
        else:
            secid = f"0.{stock_code}"
            
        url = "http://push2.eastmoney.com/api/qt/stock/get"
        params = {
            'invt': 2,
            'fltt': 2,
            'fields': 'f12,f13,f14,f6',
            'secid': secid,
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'wbp2u': '|0|0|0|web'
        }
        
        response = requests.get(url, params=params, timeout=5, 
                               proxies={'http': None, 'https': None})
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                return data['data'].get('f14')
    except Exception as e:
        print(f"  东方财富API获取 {stock_code} 名称失败: {e}")
    return None

def update_stock_names():
    """更新数据库中所有缺少股票名称的记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询所有缺少股票名称的记录
            print("查询缺少股票名称的记录...")
            cursor.execute("""
                SELECT DISTINCT stock_code 
                FROM weimu_recommendation 
                WHERE stock_name IS NULL OR stock_name LIKE '股票%'
                ORDER BY stock_code
            """)
            stocks = cursor.fetchall()
            
            print(f"找到 {len(stocks)} 只缺少股票名称的股票")
            
            if not stocks:
                print("所有记录已有股票名称")
                return
            
            # 2. 为每只股票获取名称并更新
            updated_count = 0
            failed_count = 0
            
            for stock in stocks:
                stock_code = stock['stock_code']
                print(f"\n处理股票 {stock_code}:")
                
                # 尝试多种方式获取股票名称
                stock_name = None
                
                # 方案1: akshare
                stock_name = get_stock_name_from_akshare(stock_code)
                
                # 方案2: 东方财富API
                if not stock_name:
                    stock_name = get_stock_name_from_eastmoney(stock_code)
                
                # 方案3: 如果还是没获取到，使用默认名称
                if not stock_name:
                    stock_name = f"股票{stock_code}"
                    print(f"  使用默认名称: {stock_name}")
                else:
                    print(f"  获取到名称: {stock_name}")
                
                # 更新数据库
                try:
                    cursor.execute(
                        "UPDATE weimu_recommendation SET stock_name = %s WHERE stock_code = %s",
                        (stock_name, stock_code)
                    )
                    updated_count += 1
                    print(f"  更新成功")
                except Exception as e:
                    failed_count += 1
                    print(f"  更新失败: {e}")
                
                # 控制请求频率
                time.sleep(1)
            
            # 提交事务
            conn.commit()
            
            print(f"\n" + "=" * 50)
            print(f"更新完成:")
            print(f"  成功更新: {updated_count} 只股票")
            print(f"  失败: {failed_count} 只股票")
            print("=" * 50)
            
    finally:
        conn.close()

def main():
    print("微淼选股结果股票名称更新工具")
    print("=" * 60)
    
    try:
        # 测试数据库连接
        conn = get_connection()
        conn.close()
        print("✓ 数据库连接正常")
        
        # 执行更新
        update_stock_names()
        
        print("\n操作建议:")
        print("1. 刷新财务自由页面查看更新后的股票名称")
        print("2. 运行新的筛选会自动获取股票名称")
        print("3. 如果有新的股票代码缺少名称，可再次运行此脚本")
        
    except Exception as e:
        print(f"\n❌ 执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()