#!/usr/bin/env python3
"""完整筛选流程测试"""
import sys
import os
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.weimu.screener import run_weimu_screening

def test_callback(stage, current, total, message):
    """进度回调函数"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    if stage == 'init':
        print(f'[{timestamp}] 初始化: {message}')
    elif stage == 'prefilter_done':
        print(f'[{timestamp}] 预筛选完成: {message}')
    elif stage == 'preliminary':
        if current % 10 == 0:
            print(f'[{timestamp}] 海选进度: {current}/{total}, {message}')
    elif stage == 'preliminary_done':
        print(f'[{timestamp}] 海选完成: {message}')
    elif stage == 'fine_done':
        print(f'[{timestamp}] 精选完成: {message}')
    elif stage == 'done':
        print(f'[{timestamp}] 筛选完成: {message}')
        print(f'    推荐结果: {current} 只')

def run_full_test():
    """运行完整筛选测试"""
    print('微淼完整筛选流程测试')
    print('=' * 80)
    print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 80)
    
    try:
        start_time = time.time()
        results = run_weimu_screening(callback=test_callback)
        end_time = time.time()
        
        print('\n' + '='*80)
        print('筛选结果统计:')
        print('='*80)
        
        if not results:
            print('❌ 未筛选出任何股票')
            return
        
        # 统计估值状态
        buy_count = sum(1 for r in results if r.get('valuation') == 'buy')
        hold_count = sum(1 for r in results if r.get('valuation') == 'hold')
        sell_count = sum(1 for r in results if r.get('valuation') == 'sell')
        wait_count = sum(1 for r in results if r.get('valuation') == 'wait')
        
        print(f'总筛选出: {len(results)} 只股票')
        print(f'可买入(buy): {buy_count} 只')
        print(f'持有(hold): {hold_count} 只')
        print(f'卖出(sell): {sell_count} 只')
        print(f'等待(wait): {wait_count} 只')
        
        # 显示前10只推荐股票
        print(f'\n前10只推荐股票:')
        print('-' * 120)
        print(f"{'排名':<4} {'代码':<8} {'名称':<10} {'ROE(%)':<8} {'毛利率(%)':<10} {'负债率(%)':<10} {'股息率(%)':<8} {'估值':<6} {'评分':<6}")
        print('-' * 120)
        
        # 由于没有股票名称，只显示代码
        for i, stock in enumerate(results[:10], 1):
            code = stock.get('code', '')
            roe_avg = stock.get('roe_avg', 0)
            gm_avg = stock.get('gross_margin_avg', 0)
            debt_ratio = stock.get('debt_ratio', '')
            div_yield = stock.get('dividend_yield', '')
            valuation = stock.get('valuation', '')
            score = stock.get('score', 0)
            
            # 格式化显示
            roe_str = f'{roe_avg:.1f}' if roe_avg else '-'
            gm_str = f'{gm_avg:.1f}' if gm_avg else '-'
            debt_str = f'{debt_ratio:.1f}' if debt_ratio else '-'
            div_str = f'{div_yield:.2f}' if div_yield else '-'
            
            print(f'{i:<4} {code:<8} {"-":<10} {roe_str:<8} {gm_str:<10} {debt_str:<10} {div_str:<8} {valuation:<6} {score:<6}')
        
        print('-' * 120)
        print(f'筛选耗时: {end_time - start_time:.1f} 秒')
        print(f'完成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        
    except Exception as e:
        print(f'\n❌ 筛选过程出现异常: {e}')
        import traceback
        traceback.print_exc()

def quick_test():
    """快速测试（只运行前50只股票的筛选）"""
    print('\n' + '='*80)
    print('快速筛选测试（前50只股票）')
    print('='*80)
    
    from app.stock_data.stock_pool import STOCK_POOL
    from app.stock_data.finance_data import get_finance_indicators
    from app.weimu.screener import PRELIMINARY_MIN_YEARS, PRELIMINARY_ROE_MIN, PRELIMINARY_GROSS_MARGIN_MIN
    
    stock_pool = list(STOCK_POOL)
    print(f'股票池总数: {len(stock_pool)}')
    
    # 取前50只股票测试
    test_codes = stock_pool[:50]
    print(f'测试前 {len(test_codes)} 只股票')
    
    passed_codes = []
    
    for i, code in enumerate(test_codes, 1):
        if i % 5 == 0:
            print(f'  进度: {i}/{len(test_codes)}，已通过: {len(passed_codes)}')
        
        try:
            indicators = get_finance_indicators(code)
            if not indicators:
                continue
            
            roe_list = indicators.get('roe_list', [])
            gm_list = indicators.get('gross_margin_list', [])
            
            # 检查是否通过海选
            if len(roe_list) < PRELIMINARY_MIN_YEARS or len(gm_list) < PRELIMINARY_MIN_YEARS:
                continue
            
            # 使用新的筛选逻辑
            recent_roe = roe_list[:PRELIMINARY_MIN_YEARS]
            recent_3_roe = roe_list[:3]
            roe_pass_recent = all(r >= PRELIMINARY_ROE_MIN for r in recent_3_roe)
            roe_pass_count = sum(1 for r in recent_roe if r >= PRELIMINARY_ROE_MIN)
            roe_avg = sum(recent_roe) / len(recent_roe)
            
            if not (roe_pass_recent or (roe_pass_count >= 3 and roe_avg >= 13.0)):
                continue
            
            recent_gm = gm_list[:PRELIMINARY_MIN_YEARS]
            recent_3_gm = gm_list[:3]
            gm_pass_recent = all(g >= PRELIMINARY_GROSS_MARGIN_MIN for g in recent_3_gm)
            gm_avg = sum(recent_gm) / len(recent_gm)
            gm_pass_count = sum(1 for g in recent_gm if g >= PRELIMINARY_GROSS_MARGIN_MIN)
            
            if not (gm_pass_recent or (gm_pass_count >= 3 and gm_avg >= 27.0)):
                continue
            
            passed_codes.append(code)
            
        except Exception:
            continue
        
        time.sleep(0.1)  # 控制请求频率
    
    print(f'\n快速测试完成: {len(passed_codes)}/{len(test_codes)} 只股票通过海选')
    if passed_codes:
        print(f'通过股票: {passed_codes[:10]}' + ('...' if len(passed_codes) > 10 else ''))
    else:
        print('❌ 没有股票通过海选')

if __name__ == '__main__':
    # 先运行快速测试
    quick_test()
    
    # 询问是否运行完整测试
    print('\n' + '='*80)
    response = input('是否运行完整筛选流程？耗时约5-10分钟 (y/n): ')
    if response.lower() == 'y':
        run_full_test()
    else:
        print('快速测试完成，跳过完整筛选。')