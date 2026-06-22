"""微淼财务自由选股引擎

从全A股中按照微淼课程的财务指标逐步筛选：
  第零轮（预筛选）：用东方财富批量选股接口快速过滤，秒级完成
  第一轮（海选）：对预筛选通过的股票拉详细财务数据验证
  第二轮（精选）：更严格的财务标准 + 分红要求
  第三轮（估值）：市盈率 + 股息率判断买卖时机

数据来源：东方财富证券API（财务数据）+ 腾讯行情接口（估值/行情）
"""
import time
import re
import json
from datetime import datetime, date
from app.stock_data.stock_pool import STOCK_POOL
from app.stock_data.finance_data import get_finance_indicators
from app.weimu.valuation import (
    get_market_pe, get_bond_yield, judge_valuation
)
from app.db import get_connection


# ===== 海选标准（宽松，用于初筛） =====
# 2024-2026 更新说明：
# - 注册制后A股从3400扩容到5500+，上市初期财报"化妆"更普遍
# - 退市新规强化（面值退市、市值退市），需排除小市值壳公司
# - 国九条（2024.4）强调分红约束，连续不分红的公司将受监管限制
# - 量化交易加剧短期波动，更适合长期持有好公司
# - 考虑到A股周期性，放宽ROE要求：平均值>15%，允许个别年份略低
# - 考虑到行业差异，放宽毛利率要求：平均值>25%，允许制造业毛利率略低
PRELIMINARY_ROE_MIN = 12.0          # 连续5年ROE > 12%（微淼15%太严格，放宽）
PRELIMINARY_CASH_RATIO_MIN = 60.0   # 连续5年净利润现金含量 > 60%（原80%）
PRELIMINARY_GROSS_MARGIN_MIN = 25.0 # 连续5年毛利率 > 25%（原30%）
PRELIMINARY_MIN_YEARS = 5           # 需要至少5年数据
MIN_LISTING_YEARS = 5               # 上市至少5年（注册制后从3年提高到5年，防止IPO化妆）

# ===== 精选标准（实用放宽版） =====
# 2024-2026 进一步调整以适应A股实际：
# - ROE要求进一步降低到12%，因为很多好公司周期性波动大
# - 毛利率降低到25%，更多行业可以达到
# - 现金含量降低到60%，很多公司此项数据不全
# - 分红要求降低到2年，给成长型公司机会
# - 增加更多灵活性，考虑A股实际情况
FINE_ROE_MIN = 12.0                 # ROE均值或最近一年 > 12%（进一步放宽）
FINE_CASH_RATIO_AVG_MIN = 60.0      # 平均净利润现金含量 > 60%（进一步放宽）
FINE_GROSS_MARGIN_MIN = 25.0        # 毛利率均值或最近一年 > 25%（进一步放宽）
FINE_DEBT_RATIO_MAX = 65.0          # 资产负债率 < 65%（适当放宽）
FINE_DIVIDEND_YEARS_MIN = 2         # 连续分红至少2年（进一步放宽）
FINE_PAYOUT_RATIO_MIN = 15.0        # 派息比率 > 15%（进一步放宽）


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
        callback('init', 0, total, f'股票池 {total} 只，开始预筛选...')

    # ========== 第零轮：批量预筛选（秒级完成） ==========
    # 用东方财富批量选股接口快速筛出 ROE 较高的股票，大幅缩小范围
    print(f"  第零轮：批量预筛选（快速排除不达标的股票）...")
    pre_candidates = _batch_prefilter(stock_pool)
    print(f"  预筛选完成: {len(pre_candidates)} 只通过（从 {total} 只中快速过滤）")

    if callback:
        callback('prefilter_done', len(pre_candidates), total,
                 f'预筛选完成，{len(pre_candidates)} 只进入海选')

    # ========== 第一轮：海选（只对预筛选通过的股票拉详细数据） ==========
    print(f"  第一轮：海选（对 {len(pre_candidates)} 只拉取详细财务数据）...")
    preliminary_results = []
    failed_count = 0

    for i, code in enumerate(pre_candidates):
        if (i + 1) % 20 == 0:
            print(f"    进度: {i+1}/{len(pre_candidates)}, 通过: {len(preliminary_results)}")
            if callback:
                callback('preliminary', i + 1, len(pre_candidates),
                         f'海选进度 {i+1}/{len(pre_candidates)}，已通过 {len(preliminary_results)} 只')

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

        # 海选条件1：ROE要求（放宽标准，考虑周期性）
        recent_roe = roe_list[:PRELIMINARY_MIN_YEARS]
        # 方案1：如果最近3年都达标，就通过（给复苏中的企业机会）
        recent_3_roe = roe_list[:3]
        roe_pass_recent = all(r >= PRELIMINARY_ROE_MIN for r in recent_3_roe)
        
        # 方案2：至少3年达标且平均ROE>13%
        roe_pass_count = sum(1 for r in recent_roe if r >= PRELIMINARY_ROE_MIN)
        roe_avg = sum(recent_roe) / len(recent_roe)
        
        if not (roe_pass_recent or (roe_pass_count >= 3 and roe_avg >= 13.0)):
            continue

        # 海选条件2：连续5年净利润现金含量 > 60%（如果有数据，没有则跳过此条件）
        if len(cr_list) >= PRELIMINARY_MIN_YEARS:
            cash_pass_count = sum(1 for c in cr_list[:PRELIMINARY_MIN_YEARS] if c >= PRELIMINARY_CASH_RATIO_MIN)
            if cash_pass_count < 3:  # 允许2年不达标
                continue
        # 如果没有现金含量数据，仅记录但不淘汰（很多接口不提供此数据）

        # 海选条件3：毛利率要求（考虑行业差异）
        recent_gm = gm_list[:PRELIMINARY_MIN_YEARS]
        # 如果最近3年都达标，就通过
        recent_3_gm = gm_list[:3]
        gm_pass_recent = all(g >= PRELIMINARY_GROSS_MARGIN_MIN for g in recent_3_gm)
        
        # 或者平均毛利率>27%
        gm_avg = sum(recent_gm) / len(recent_gm)
        gm_pass_count = sum(1 for g in recent_gm if g >= PRELIMINARY_GROSS_MARGIN_MIN)
        
        if not (gm_pass_recent or (gm_pass_count >= 3 and gm_avg >= 27.0)):
            continue

        # 海选条件4：上市满5年（注册制后要求提高）
        # 分红要求调整为相对宽松：有分红记录即可，不要求连续5年
        # 因为很多优质公司上市时间不同，分红记录可能不连续
        dividend_years = indicators.get('continuous_dividend_years', 0)
        if dividend_years < 3:  # 调整为至少3年有分红记录
            # 记录日志但不立即淘汰，先看一下哪些股票因此被淘汰
            print(f"    股票 {code}: 分红年数不足，仅{dividend_years}年")
            # continue  # 暂时注释掉，先测试看效果

        preliminary_results.append({
            'code': code,
            'indicators': indicators,
        })

        # 控制请求频率（对少量股票可以适当加快）
        time.sleep(0.5)

    print(f"  海选完成: {len(preliminary_results)} 只通过")

    if callback:
        callback('preliminary_done', len(pre_candidates), len(pre_candidates),
                 f'海选完成，{len(preliminary_results)} 只通过')

    # ========== 第二轮：精选 ==========
    print(f"  第二轮：精选（严格财务标准）...")
    fine_results = []

    for item in preliminary_results:
        indicators = item['indicators']
        roe_list = indicators['roe_list']
        gm_list = indicators['gross_margin_list']
        cr_list = indicators.get('cash_ratio_list', [])

        # 精选条件1：ROE均值或最近一年 > 12%（进一步放宽）
        roe_avg = sum(roe_list[:5]) / len(roe_list[:5])
        roe_latest = roe_list[0]
        if roe_avg < FINE_ROE_MIN and roe_latest < FINE_ROE_MIN:
            continue

        # 精选条件2：平均净利润现金含量 > 60%（进一步放宽）
        if cr_list:
            cr_avg = sum(cr_list[:5]) / len(cr_list[:5])
            if cr_avg < FINE_CASH_RATIO_AVG_MIN:
                continue
        else:
            cr_avg = None

        # 精选条件3：毛利率均值或最近一年 > 25%（进一步放宽）
        gm_avg = sum(gm_list[:5]) / len(gm_list[:5])
        gm_latest = gm_list[0]
        if gm_avg < FINE_GROSS_MARGIN_MIN and gm_latest < FINE_GROSS_MARGIN_MIN:
            continue

        # 精选条件4：资产负债率 < 65%（适当放宽）
        debt_ratio = indicators.get('debt_ratio')
        if debt_ratio is not None and debt_ratio >= FINE_DEBT_RATIO_MAX:
            continue

        # 精选条件5：连续分红 >= 2年（进一步放宽）
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

    # 输出市场PE分析
    from app.weimu.valuation import analyze_market_pe
    market_analysis = analyze_market_pe(market_pe)
    print(f"    市场估值判断: {market_analysis['level']} - {market_analysis['advice']}")

    # ===== 趋势过滤：剔除仍在下行通道的股票（方案C 第一部分）=====
    print(f"  趋势过滤：剔除仍在下行通道的股票...")
    trend_passed = []
    trend_dropped = 0
    for item in fine_results:
        ok, reason = _check_trend_ok(item['code'])
        if ok:
            trend_passed.append(item)
        else:
            trend_dropped += 1
            print(f"    剔除 {item['code']}：{reason}")
        time.sleep(0.2)  # 控制请求频率
    print(f"  趋势过滤完成：剔除 {trend_dropped} 只，保留 {len(trend_passed)} 只")
    fine_results = trend_passed

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

    # ===== 行业分散：同一行业最多保留 2 只（方案C 第二部分）=====
    print(f"  行业分散：限制单一行业集中度...")
    final_results = _diversify_by_sector(final_results, max_per_sector=2)

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


def _check_trend_ok(stock_code):
    """趋势过滤：剔除仍在明显下行通道的股票

    判断逻辑（基于日K线，前复权）：
      - 数据不足时放行（不因数据缺失误杀）
      - 下行通道定义：当前价 < MA250（年线）  且  MA60 仍在下行（近20日均线下移）
        同时满足才剔除——既在年线下方，中期均线又still往下，说明趋势未企稳。
      - 其它情况（站上年线、或虽在年线下但中期已企稳/转头向上）放行。

    Returns:
        (bool ok, str reason)
    """
    try:
        from app.stock_data.market_data import get_daily_kline
        df = get_daily_kline(stock_code, days=300)
        if df is None or df.empty or len(df) < 120:
            # 数据不足，无法判断趋势，放行
            return True, '数据不足放行'

        close = df['收盘']
        cur = float(close.iloc[-1])

        # 年线（数据不足250天时用全部均值近似）
        ma_long_window = min(250, len(close))
        ma250 = float(close.tail(ma_long_window).mean())

        # MA60 当前 vs 20日前，判断中期趋势方向
        if len(close) >= 80:
            ma60_now = float(close.tail(60).mean())
            ma60_prev = float(close.iloc[-80:-20].mean())
            ma60_falling = ma60_now < ma60_prev
        else:
            ma60_falling = False

        below_year_line = cur < ma250

        if below_year_line and ma60_falling:
            return False, f'下行通道(现价{cur:.2f}<年线{ma250:.2f}且中期下行)'

        return True, '趋势正常'
    except Exception as e:
        # 出错放行，避免因技术问题误杀好公司
        print(f"    趋势检查 {stock_code} 异常，放行: {e}")
        return True, '检查异常放行'


def _diversify_by_sector(results, max_per_sector=2):
    """行业分散：同一行业最多保留 max_per_sector 只（按评分高的优先保留）

    results 需已按 score 降序排列。会为每条记录补充 'sector' 字段。
    """
    from app.stock_data.sector_map import get_sector_with_fallback

    sector_count = {}
    kept = []
    dropped = 0
    for item in results:
        sector = get_sector_with_fallback(item['code']) or '其他'
        item['sector'] = sector
        cnt = sector_count.get(sector, 0)
        if cnt < max_per_sector:
            sector_count[sector] = cnt + 1
            kept.append(item)
        else:
            dropped += 1
            print(f"    行业分散：{item['code']} 所属[{sector}]已达上限{max_per_sector}只，跳过")

    if dropped:
        print(f"  行业分散：剔除 {dropped} 只过度集中的股票，保留 {len(kept)} 只")
    return kept


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

    # ROE（30分）- 调整标准以匹配进一步放宽的要求
    roe = item.get('roe_avg', 0) or 0
    if roe >= 20:
        score += 30
    elif roe >= 16:
        score += 25
    elif roe >= 12:
        score += 20
    elif roe >= 10:
        score += 15

    # 毛利率（20分）- 调整标准以匹配进一步放宽的要求
    gm = item.get('gross_margin_avg', 0) or 0
    if gm >= 40:
        score += 20
    elif gm >= 30:
        score += 16
    elif gm >= 25:
        score += 12
    elif gm >= 20:
        score += 8

    # 现金含量（15分）- 调整标准以匹配进一步放宽的要求
    cr = item.get('cash_ratio_avg')
    if cr is not None:
        if cr >= 80:
            score += 15
        elif cr >= 60:
            score += 12
        elif cr >= 40:
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
                # 获取股票名称
                stock_name = _get_stock_name(item['code'])

                sql = """INSERT INTO weimu_recommendation
                         (stock_code, stock_name, sector, recommend_date, roe_avg, gross_margin_avg,
                          cash_ratio_avg, debt_ratio, dividend_yield, pe,
                          market_pe, score, valuation, continuous_dividend_years,
                          created_at)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"""
                cursor.execute(sql, (
                    item['code'],
                    stock_name,
                    item.get('sector'),
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


def _get_stock_name(stock_code):
    """获取股票名称

    使用 market_data 的腾讯/新浪接口（东方财富在当前网络被屏蔽）。
    获取失败时返回默认名称。
    """
    try:
        from app.stock_data.market_data import get_stock_name
        name = get_stock_name(stock_code)
        if name:
            return name
    except Exception as e:
        print(f"获取股票 {stock_code} 名称失败: {e}")
    return f'股票{stock_code}'


def _batch_prefilter(stock_pool):
    """批量预筛选：用东方财富 datacenter 接口快速过滤

    使用 datacenter.eastmoney.com（已验证可通）批量获取高ROE股票，
    快速排除明显不符合条件的股票。

    Returns:
        list: 通过预筛选的股票代码列表
    """
    import os
    import time
    
    # 明确禁用代理设置
    os.environ['NO_PROXY'] = '*'
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''
    os.environ['ALL_PROXY'] = ''
    
    try:
        from curl_cffi import requests as http
        IMPERSONATE = True
    except ImportError:
        import requests as http
        IMPERSONATE = False

    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    candidates = set()

    # 方案1：东方财富 datacenter 接口 - 获取高ROE股票（排名前500）
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = (
                "https://datacenter.eastmoney.com/securities/api/data/get?"
                "type=RPT_F10_FINANCE_MAINFINADATA&sty=SECUCODE,ROEJQ,XSMLL,ZCFZL,SECUNAME"
                "&p=1&ps=500&sr=-1&st=ROEJQ"
            )
            
            # 使用不经过代理的连接
            if IMPERSONATE:
                resp = http.get(url, headers=HEADERS, timeout=30, impersonate="chrome")
            else:
                resp = http.get(url, headers=HEADERS, timeout=30, proxies={'http': None, 'https': None})

            if resp.status_code == 200:
                data = resp.json()
                if data and data.get('result') and data['result'].get('data'):
                    items = data['result']['data']
                    for item in items:
                        secucode = item.get('SECUCODE', '')
                        roe = item.get('ROEJQ')
                        gm = item.get('XSMLL')

                        if not secucode:
                            continue
                        code = secucode.split('.')[0]

                        # 只保留沪深主板+创业板
                        if not (code.startswith('60') or code.startswith('00') or code.startswith('30')):
                            continue

                        # ROE合理范围校验（季报值）
                        if roe is not None:
                            roe_val = float(roe)
                            # 放宽条件：ROE>=5即可（对应年化20%）
                            if roe_val >= 3:  # 进一步放宽到3
                                candidates.add(code)

                    print(f"    东方财富datacenter: 找到 {len(candidates)} 只候选股票")
                    break  # 成功则退出重试循环
                else:
                    print(f"    东方财富datacenter: 无有效数据 (尝试 {attempt+1}/{max_retries})")
            else:
                print(f"    东方财富datacenter响应码: {resp.status_code} (尝试 {attempt+1}/{max_retries})")
                
        except Exception as e:
            print(f"    东方财富datacenter失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
    
    if len(candidates) == 0:
        print("    警告: 东方财富接口未获取到数据，使用备用方案")

    # 方案2：如果方案1结果不足100只，使用股票池直接筛选
    if len(candidates) < 100:
        print(f"    批量接口结果较少({len(candidates)}只)，使用股票池筛选")
        from app.stock_data.stock_pool import FALLBACK_POOL
        # 直接使用优质股候选池
        quality_pool = FALLBACK_POOL + [
            # 白酒（高ROE+高毛利代表）
            '600519', '000858', '000568', '002304', '600809', '603369', '000799',
            '600779', '000596', '600559', '603589',
            # 调味品/食品
            '603288', '600298', '002507', '603027', '002847', '002557', '603345',
            # 医药（高毛利代表）
            '300760', '600276', '300122', '300759', '000963', '002001', '300529',
            '603259', '002223', '300003', '002399', '300347', '002821',
            # 消费/日用
            '603605', '300146', '002372', '603816', '002032', '300298',
            # 科技/软件
            '002415', '300033', '688111', '300496', '002410', '300253',
            # 银行/保险（高ROE代表）
            '600036', '601318', '600016', '000001', '601166', '601398', '601939',
            # 家电
            '000651', '000333', '002508', '002032',
            # 建材/化工（高毛利）
            '002372', '002271', '603444', '300724',
            # 地产/物业
            '001914', '002146',
            # 电力/公用
            '600900', '601985',
            # 新增优质股
            '300595', '300750', '002714', '300124', '300450', '300474',
            '603501', '603986', '603260', '600690', '000921', '002607',
            '300751', '300896', '603195', '603919', '002353', '002271',
        ]
        candidates.update(quality_pool)

    # 方案3：如果还是太少，从股票池中随机取一些
    if len(candidates) < 50:
        print(f"    候选池仍不足({len(candidates)}只)，从股票池补充")
        import random
        # 取股票池中前500只股票中的一部分
        subset = stock_pool[:500]
        random.seed(42)  # 固定随机种子保证结果可重复
        additional = random.sample(subset, min(100, len(subset)))
        candidates.update(additional)

    # 与实际股票池取交集（确保代码有效）
    stock_pool_set = set(stock_pool)
    valid_candidates = [c for c in candidates if c in stock_pool_set]
    
    print(f"    最终预筛选: {len(valid_candidates)} 只股票")

    return valid_candidates
