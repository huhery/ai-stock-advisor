"""测试history接口"""
import sys
sys.path.append('.')
from app.screening.engine import get_history_recommendations, get_today_recommendations, get_available_dates

print("1. 今日推荐:")
today = get_today_recommendations()
print(f"   数量: {len(today)}")
if today:
    print(f"   示例: {today[0].get('stock_name')} - 板块: '{today[0].get('sector', '')}'")

print("\n2. 历史推荐 (2026-06-11):")
history = get_history_recommendations('2026-06-11')
print(f"   数量: {len(history)}")
if history:
    print(f"   示例: {history[0].get('stock_name')} - 板块: '{history[0].get('sector', '')}'")

print("\n3. 历史推荐 (2026-06-10):")
history2 = get_history_recommendations('2026-06-10')
print(f"   数量: {len(history2)}")
if history2:
    print(f"   示例: {history2[0].get('stock_name')} - 板块: '{history2[0].get('sector', '')}'")

print("\n4. 可用日期列表:")
dates = get_available_dates()
print(f"   {dates}")
