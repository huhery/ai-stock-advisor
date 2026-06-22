#!/usr/bin/env python3
"""测试微淼筛选器修复效果"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.stock_data.finance_data import get_finance_indicators
from app.weimu.screener import PRELIMINARY_ROE_MIN, PRELIMINARY_GROSS_MARGIN_MIN, PRELIMINARY_MIN_YEARS

def test_quality_stocks():
    """测试公认的优质股是否能够通过海选"""
    # 优质股列表：贵州茅台、海天味业、海康威视、格力电器、伟星新材、五粮液
    quality_stocks = [
        {'code': '600519', 'name': '贵州茅台', 'reason': '白酒龙头，高ROE高毛利'},
        {'code': '603288', 'name': '海天味业', 'reason': '调味品龙头，高毛利'},
        {'code': '002415', 'name': '海康威视', 'reason': '安防龙头，稳定ROE'},
        {'code': '000651', 'name': '格力电器', 'reason': '家电龙头，高分红'},
        {'code': '002372', 'name': '伟星新材', 'reason': '管材龙头，高毛利'},
        {'code': '000858', 'name': '五粮液', 'reason': '白酒龙头'},
        {'code': '600036', 'name': '招商银行', 'reason': '银行龙头，高ROE'},
        {'code': '300760', 'name': '迈瑞医疗', 'reason': '医疗设备龙头'},
        {'code': '002304', 'name': '洋河股份', 'reason': '白酒龙头'},
        {'code': '000568', 'name': '泸州老窖', 'reason': '白酒龙头'},
    ]
    
    print('微淼筛选器测试 - 优质股验证')
    print('=' * 80)
    
    passed_count = 0
    total_count = len(quality_stocks)
    
    for stock in quality_stocks:
        print(f'\n股票: {stock["name"]} ({stock["code"]}) - {stock["reason"]}')
        
        try:
            indicators = get_finance_indicators(stock['code'])
            if not indicators:
                print(f'  ❌ 无法获取数据')
                continue
            
            roe_list = indicators.get('roe_list', [])
            gm_list = indicators.get('gross_margin_list', [])
            cr_list = indicators.get('cash_ratio_list', [])
            div_years = indicators.get('continuous_dividend_years', 0)
            
            print(f'  ROE数据: {roe_list[:5] if roe_list else []}')
            print(f'  毛利率: {gm_list[:5] if gm_list else []}')
            print(f'  现金含量: {cr_list[:5] if cr_list else "无数据"}')
            print(f'  分红年数: {div_years}年')
            
            # 检查条件
            failed_reasons = []
            
            # 条件1: 连续5年ROE > 15%
            if len(roe_list) < PRELIMINARY_MIN_YEARS:
                failed_reasons.append(f'ROE数据不足({len(roe_list)}年)')
            elif not all(r >= PRELIMINARY_ROE_MIN for r in roe_list[:PRELIMINARY_MIN_YEARS]):
                failed_reasons.append(f'ROE不达标')
                print(f'  ROE详细: {roe_list[:5]}')
            
            # 条件2: 连续5年毛利率 > 30%
            if len(gm_list) < PRELIMINARY_MIN_YEARS:
                failed_reasons.append(f'毛利率数据不足({len(gm_list)}年)')
            elif not all(g >= PRELIMINARY_GROSS_MARGIN_MIN for g in gm_list[:PRELIMINARY_MIN_YEARS]):
                failed_reasons.append(f'毛利率不达标')
                print(f'  毛利率详细: {gm_list[:5]}')
            
            # 条件3: 分红记录（宽松）
            if div_years < 3:
                print(f'  注意: 分红年数较少({div_years}年)，但通过')
                # 不因此淘汰
            
            if not failed_reasons:
                print(f'  ✅ 通过海选')
                passed_count += 1
            else:
                print(f'  ❌ 未通过: {", ".join(failed_reasons)}')
                
        except Exception as e:
            print(f'  ⚠️ 测试异常: {e}')
    
    print(f'\n{'='*80}')
    print(f'测试结果: {passed_count}/{total_count} 只优质股通过海选')
    
    if passed_count == 0:
        print('❌ 所有优质股都无法通过，需要继续调整筛选条件')
    elif passed_count < total_count * 0.5:
        print('⚠️ 通过率较低，可能需要进一步放宽条件')
    else:
        print('✅ 筛选器能识别大部分优质股')

def run_quick_screening():
    """快速运行筛选测试"""
    print('\n' + '='*80)
    print('快速筛选测试（前20只预筛选股票）')
    print('='*80)
    
    # 导入筛选器
    from app.stock_data.stock_pool import STOCK_POOL
    from app.weimu.screener import _batch_prefilter
    
    stock_pool = list(STOCK_POOL)
    print(f'股票池总数: {len(stock_pool)}')
    
    # 运行预筛选
    pre_candidates = _batch_prefilter(stock_pool)
    print(f'预筛选结果: {len(pre_candidates)} 只')
    
    # 测试前10只股票的详细筛选
    test_codes = pre_candidates[:10] if len(pre_candidates) > 10 else pre_candidates
    print(f'\n测试前 {len(test_codes)} 只股票的详细筛选:')
    
    for i, code in enumerate(test_codes, 1):
        print(f'\n{i}. 股票 {code}:')
        try:
            indicators = get_finance_indicators(code)
            if not indicators:
                print('  无数据')
                continue
                
            roe_list = indicators.get('roe_list', [])
            gm_list = indicators.get('gross_margin_list', [])
            div_years = indicators.get('continuous_dividend_years', 0)
            
            # 检查是否通过海选
            passed = True
            reason = []
            
            if len(roe_list) < 5:
                passed = False
                reason.append(f'ROE数据不足({len(roe_list)})')
            elif not all(r >= 15 for r in roe_list[:5]):
                passed = False
                reason.append(f'ROE不达标({roe_list[:3]}...)')
            
            if len(gm_list) < 5:
                passed = False
                reason.append(f'毛利率数据不足({len(gm_list)})')
            elif not all(g >= 30 for g in gm_list[:5]):
                passed = False
                reason.append(f'毛利率不达标({gm_list[:3]}...)')
            
            if div_years < 3:
                print(f'  分红较少({div_years}年)，但不淘汰')
            
            if passed:
                print(f'  ✅ 通过')
            else:
                print(f'  ❌ 未通过: {", ".join(reason)}')
                
        except Exception as e:
            print(f'  ⚠️ 异常: {e}')

if __name__ == '__main__':
    print('微淼筛选器修复测试')
    print('=' * 80)
    
    # 先测试优质股
    test_quality_stocks()
    
    # 运行快速筛选测试
    run_quick_screening()