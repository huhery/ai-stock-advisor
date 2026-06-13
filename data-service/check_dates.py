"""检查数据库中有哪些日期的选股记录"""
import sys
sys.path.append('.')
from app.db import get_connection

conn = get_connection()
try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT recommend_date, COUNT(*) as cnt FROM stock_recommendation GROUP BY recommend_date ORDER BY recommend_date DESC")
        results = cursor.fetchall()
        print("数据库中的选股记录日期:")
        if results:
            for r in results:
                print(f"  {r['recommend_date']} - {r['cnt']}只股票")
        else:
            print("  (无记录)")
        
        print(f"\n总记录数: {sum(r['cnt'] for r in results) if results else 0}")
finally:
    conn.close()
