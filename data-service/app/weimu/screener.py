"""微淼财务自由选股引擎

从全A股中按照微淼课程的财务指标逐步筛选：
  第一轮（海选）：ROE/现金含量/毛利率 基础过滤
  第二轮（精选）：更严格的财务标准 + 分红要求
  第三轮（估值）：市盈率 + 股息率判断买卖时机

数据来源：东方财富证券API（财务数据）+ 腾讯行情接口（估值/行情）
"""
import time
import json
from datetime import datetime, date
from app.stock_data.stock_pool import STOCK_POOL
from app.stock_data.finance_data import get_finance_indicators
from app.weimu.valuation import (
    get_market_pe, get_bond_yield, judge_valuation
)
from app.db import get_connection


# ===== 海选标准（宽松，用于初筛） =====
PRELIMINARY_ROE_MIN = 15.0          # 连续5年ROE > 15%
PRELIMINARY_CASH_RATIO_MIN = 80.0   # 连续5年净利润现金含量 > 80%
PRELIMINARY_GROSS_MARGIN_MIN = 30.0 # 连续5年毛利率 > 30%
PRELIMINARY_MIN_YEARS = 5           # 需要至少5年数据
MIN_LISTING_YEARS = 3               # 上市至少3年

# ===== 精选标准（严格） =====
FINE_ROE_MIN = 20.0                 # ROE均值或最近一年 > 20%
FINE_CASH_RATIO_AVG_MIN = 100.0     # 平均净利润现金含量 > 100%
FINE_GROSS_MARGIN_MIN = 40.0        # 毛利率均值或最近一年 > 40%
FINE_DEBT_RATIO_MAX = 60.0          # 资产负债率 < 60%
FINE_DIVIDEND_YEARS_MIN = 5         # 连续分红至少5年
FINE_PAYOUT_RATIO_MIN = 25.0        # 派息比率 > 25%


def run_weimu_screening(callback=None):
    """执行完整的微淼财务自由选股

    Args:
        callback: 进度回调函数 callback(stage, current, total, message)

    Returns:
        list: 最终推荐结果
    """
    print(f"[{datetime.now()}] ===== 微淼财务自由选股开始 =====")

    # 获取股票池
    stock_pool = list(STOCK_POOL)
    total = len(stock_pool)
    print(f"  股票池总数: {total}")

    if callback:
        callback('init', 0, total, f'股票池 {total} 只，开始海选...')

    # ========== 第一轮：海选 ==========
    print(f"  第一轮：海选（财务指标基础过滤）...")
    preliminary_results = []
    failed_count = 0

    for i, code in enumerate(stock_pool):
        if (i + 1) % 100 == 0:
            print(f"    进度: {i+1}/{total}, 通过: {len(preliminary_results)}, 失败: {failed_count}")
            if callback:
                callback('preliminary', i + 1, total,
                         f'海选进度 {i+1}/{total}，已通过 {len(preliminary_results)} 只')

        # 获取财务指标
        indicators = get_finance_indicators(code)
        if not indicators:
            failed_count += 1
            continue

        # 检查数据量是否足够
        roe_list = indicators.get('roe_list', [])
        gm_list = indicators.get('gross_margin_list', [])
        cr_list = indicators.get('cash_ratio_list', [])

        if len(roe_list) < PRELIMINARY_MIN_YEARS:
            continue
        if len(gm_list) < PRELIMINARY_MIN_YEARS:
            continue

        # 海选条件1：连续5年ROE > 15%
        if not all(r >= PRELIMINARY_ROE_MIN for r in roe_list[:PRELIMINARY_MIN_YEARS]):
            continue

        # 海选条件2：连续5年净利润现金含量 > 80%（如果有数据）
        if len(cr_list) >= PRELIMINARY_MIN_YEARS:
            if not all(c >= PRELIMINARY_CASH_RATIO_MIN for c in cr_list[:PRELIMINARY_MIN_YEARS]):
                continue

        # 海选条件3：连续5年毛利率 > 30%
        if not all(g >= PRELIMINARY_GROSS_MARGIN_MIN for g in gm_list[:PRELIMINARY_MIN_YEARS]):
            continue

        # 海选条件4：连续分红 >= 3年（上市3年以上的代理指标）
        dividend_years = indicators.get('continuous_dividend_years', 0)
        if dividend_years < MIN_LISTING_YEARS:
            continue

        preliminary_results.append({
            'code': code,
            'indicators': indicators,
        })

        # 控制请求频率
        time.sleep(0.8)

    print(f"  海选完成: {len(preliminary_results)} 只通过（共扫描 {total} 只）")

    if callback:
        callback('preliminary_done', total, total,
                 f'海选完成，{len(preliminary_results)} 只通过')

    # ========== 第二轮：精选 ==========
    print(f"  第二轮：精选（严格财务标准）...")
    fine_results = []

    for item in preliminary_results:
        indicators = item['indicators']
        roe_list = indicators['roe_list']
        gm_list = indicators['gross_margin_list']
        cr_list = indicators.get('cash_ratio_list', [])

        # 精选条件1：ROE均值或最近一年 > 20%
        roe_avg = sum(roe_list[:5]) / len(roe_list[:5])
        roe_latest = roe_list[0]
        if roe_avg < FINE_ROE_MIN and roe_latest < FINE_ROE_MIN:
            continue

        # 精选条件2：平均净利润现金含量 > 100%
        if cr_list:
            cr_avg = sum(cr_list[:5]) / len(cr_list[:5])
            if cr_avg < FINE_CASH_RATIO_AVG_MIN:
                continue
        else:
            cr_avg = None

        # 精选条件3：毛利率均值或最近一年 > 40%
        gm_avg = sum(gm_list[:5]) / len(gm_list[:5])
        gm_latest = gm_list[0]
        if gm_avg < FINE_GROSS_MARGIN_MIN and gm_latest < FINE_GROSS_MARGIN_MIN:
            continue

        # 精选条件4：资产负债率 < 60%
        debt_ratio = indicators.get('debt_ratio')
        if debt_ratio is not None and debt_ratio >= FINE_DEBT_RATIO_MAX:
            continue

        # 精选条件5：连续分红 >= 5年
        dividend_years = indicators.get('continuous_dividend_years', 0)
        if dividend_years < FINE_DIVIDEND_YEARS_MIN:
            continue

        fine_results.append({
            'code': item['code'],
            'roe_avg': round(roe_avg, 2),
            'roe_latest': round(roe_latest, 2),
            'gross_margin_avg': round(gm_avg, 2),
            'gross_margin_latest': round(gm_latest, 2),
            'cash_ratio_avg': round(cr_avg, 2) if cr_avg else None,
            'debt_ratio': round(debt_ratio, 2) if debt_ratio else None,
            'dividend_yield': indicators.get('dividend_yield'),
            'pe': indicators.get('pe'),
            'pb': indicators.get('pb'),
            'continuous_dividend_years': dividend_years,
        })

    print(f"  精选完成: {len(fine_results)} 只通过")

    if callback:
        callback('fine_done', len(fine_results), len(preliminary_results),
                 f'精选完成，{len(fine_results)} 只通过')

    # ========== 第三轮：估值判断 ==========
    print(f"  第三轮：估值判断（市盈率 + 股息率）...")
    market_pe = get_market_pe()
    bond_yield = get_bond_yield()
    print(f"    深证A股整体PE: {market_pe}, 10年国债收益率: {bond_yield}%")

    final_results = []
    for item in fine_results:
        valuation = judge_valuation(
            stock_pe=item['pe'],
            market_pe=market_pe,
            dividend_yield=item['dividend_yield'],
            bond_yield=bond_yield,
        )
        item['market_pe'] = market_pe
        item['bond_yield'] = bond_yield
        item['valuation'] = valuation  # 'buy' / 'hold' / 'sell' / 'wait'
        item['score'] = _calculate_score(item)
        final_results.append(item)

    # 按评分排序
    final_results.sort(key=lambda x: x['score'], reverse=True)

    # 保存结果
    _save_results(final_results)

    print(f"[{datetime.now()}] ===== 微淼选股完成 =====")
    print(f"  总结: 海选 {len(preliminary_results)} 只 → 精选 {len(fine_results)} 只")
    buy_count = sum(1 for r in final_results if r['valuation'] == 'buy')
    print(f"  当前可买入: {buy_count} 只")

    if callback:
        callback('done', len(final_results), len(final_results),
                 f'选股完成，精选 {len(fine_results)} 只，可买入 {buy_count} 只')

    return final_results


def _calculate_score(item):
    """综合评分（满分100）

    评分维度：
    - ROE水平（30分）
    - 毛利率（20分）
    - 现金含量（15分）
    - 负债率（15分）
    - 分红持续性（10分）
    - 估值吸引力（10分）
    """
    score = 0

    # ROE（30分）
    roe = item.get('roe_avg', 0) or 0
    if roe >= 30:
        score += 30
    elif roe >= 25:
        score += 25
    elif roe >= 20:
        score += 20
    elif roe >= 15:
        score += 15

    # 毛利率（20分）
    gm = item.get('gross_margin_avg', 0) or 0
    if gm >= 60:
        score += 20
    elif gm >= 50:
        score += 16
    elif gm >= 40:
        score += 12
    elif gm >= 30:
        score += 8

    # 现金含量（15分）
    cr = item.get('cash_ratio_avg')
    if cr is not None:
        if cr >= 120:
            score += 15
        elif cr >= 100:
            score += 12
        elif cr >= 80:
            score += 8

    # 负债率（15分，越低越好）
    debt = item.get('debt_ratio')
    if debt is not None:
        if debt < 30:
            score += 15
        elif debt < 40:
            score += 12
        elif debt < 50:
            score += 9
        elif debt < 60:
            score += 5

    # 分红持续性（10分）
    div_years = item.get('continuous_dividend_years', 0)
    if div_years >= 10:
        score += 10
    elif div_years >= 7:
        score += 8
    elif div_years >= 5:
        score += 5

    # 估值吸引力（10分）
    valuation = item.get('valuation', '')
    if valuation == 'buy':
        score += 10
    elif valuation == 'hold':
        score += 5

    return score


def _save_results(results):
    """保存筛选结果到数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 清除今天的旧数据
            cursor.execute(
                "DELETE FROM weimu_recommendation WHERE recommend_date = CURDATE()"
            )

            for item in results:
                sql = """INSERT INTO weimu_recommendation
                         (stock_code, recommend_date, roe_avg, gross_margin_avg,
                          cash_ratio_avg, debt_ratio, dividend_yield, pe,
                          market_pe, score, valuation, continuous_dividend_years,
                          created_at)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"""
                cursor.execute(sql, (
                    item['code'],
                    date.today(),
                    item.get('roe_avg'),
                    item.get('gross_margin_avg'),
                    item.get('cash_ratio_avg'),
                    item.get('debt_ratio'),
                    item.get('dividend_yield'),
                    item.get('pe'),
                    item.get('market_pe'),
                    item.get('score'),
                    item.get('valuation'),
                    item.get('continuous_dividend_years'),
                ))
        conn.commit()
    finally:
        conn.close()
