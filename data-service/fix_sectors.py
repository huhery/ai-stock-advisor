"""修复数据库中已有推荐记录的板块字段"""
import sys
sys.path.append('.')
from app.db import get_connection
from app.stock_data.sector_map import get_sector_with_fallback

conn = get_connection()
try:
    with conn.cursor() as cursor:
        # 查找板块为空的记录
        cursor.execute("SELECT id, stock_code, stock_name FROM stock_recommendation WHERE sector IS NULL OR sector = ''")
        rows = cursor.fetchall()
        print(f"需要补充板块的记录: {len(rows)} 条")
        
        updated = 0
        for row in rows:
            code = row['stock_code']
            sector = get_sector_with_fallback(code)
            if sector:
                cursor.execute("UPDATE stock_recommendation SET sector = %s WHERE id = %s", (sector, row['id']))
                print(f"  {code} {row['stock_name']} → {sector}")
                updated += 1
            else:
                print(f"  {code} {row['stock_name']} → (未找到板块)")
        
        conn.commit()
        print(f"\n完成，已更新 {updated}/{len(rows)} 条记录")
finally:
    conn.close()
