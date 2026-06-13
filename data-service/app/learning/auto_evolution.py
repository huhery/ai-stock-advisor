"""全自动进化模块

每周自动执行完整的策略进化闭环：
1. 补充最新K线数据到缓存（为回测做准备）
2. 运行遗传算法回测进化
3. 如果新策略优于当前策略，自动应用
4. 调用AI分析失败案例，建议新规则
5. 自动激活AI建议中置信度高的规则
6. 记录进化日志

目标：持续优化选股策略，提升胜率和收益率。
"""
import json
import time
from datetime import datetime, timedelta
from app.db import get_connection


def run_weekly_evolution():
    """每周自动进化的完整流程

    无需人工干预，自动完成：
    数据补充 → 回测进化 → 评估对比 → 应用/回滚 → AI分析 → 记录日志
    """
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] 🧬 开始每周自动进化...")
    print(f"{'='*60}")

    log = {
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'steps': [],
        'result': 'pending'
    }

    try:
        # Step 1: 补充最近的K线缓存数据
        step1 = _step_refresh_cache()
        log['steps'].append(step1)

        # Step 2: 获取当前策略的实盘表现作为基线
        step2 = _step_get_baseline()
        log['steps'].append(step2)

        # Step 3: 运行遗传算法进化
        step3 = _step_run_evolution()
        log['steps'].append(step3)

        # Step 4: 对比进化结果和基线，决定是否应用
        step4 = _step_evaluate_and_apply(step2, step3)
        log['steps'].append(step4)

        # Step 5: AI分析失败案例并建议新规则
        step5 = _step_ai_analysis()
        log['steps'].append(step5)

        log['result'] = 'success'
        log['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    except Exception as e:
        log['result'] = 'error'
        log['error'] = str(e)
        print(f"  ❌ 进化流程异常: {e}")

    # 保存进化日志
    _save_evolution_log(log)

    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] 🧬 每周自动进化完成: {log['result']}")
    print(f"{'='*60}\n")


def _step_refresh_cache():
    """Step 1: 补充最近K线数据到缓存"""
    print(f"\n--- Step 1: 补充K线缓存 ---")
    step = {'name': 'refresh_cache', 'status': 'running'}

    try:
        from app.stock_data.cache import get_kline_cached, _save_to_db
        from app.stock_data.stock_pool import FALLBACK_POOL
        from app.screening.engine import fetch_kline_tencent

        # 用腾讯接口补充最近60天的K线到缓存（用于回测）
        # 只补充兜底池中的核心股票，避免请求过多
        success = 0
        for code in FALLBACK_POOL[:50]:
            kline = fetch_kline_tencent(code, days=60)
            if kline is not None and len(kline) >= 20:
                # 转换格式并存入缓存
                import pandas as pd
                cache_df = pd.DataFrame({
                    '日期': kline['日期'],
                    '开盘': kline['开盘'],
                    '收盘': kline['收盘'],
                    '最高': kline['最高'],
                    '最低': kline['最低'],
                    '成交量': kline['成交量'],
                    '成交额': [0] * len(kline),
                })
                _save_to_db(code, cache_df)
                success += 1
            time.sleep(0.5)

        step['status'] = 'done'
        step['detail'] = f'补充了 {success}/{min(50, len(FALLBACK_POOL))} 只股票的K线缓存'
        print(f"  ✅ {step['detail']}")

    except Exception as e:
        step['status'] = 'error'
        step['error'] = str(e)
        print(f"  ⚠️ 缓存补充失败: {e}（继续执行）")

    return step


def _step_get_baseline():
    """Step 2: 获取当前策略的实盘表现基线"""
    print(f"\n--- Step 2: 获取当前策略基线 ---")
    step = {'name': 'baseline', 'status': 'running'}

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # 统计最近30天的实盘表现
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as wins,
                        AVG(change_pct) as avg_return,
                        MAX(change_pct) as max_return,
                        MIN(change_pct) as min_return
                    FROM recommendation_tracking
                    WHERE days_after = 5
                    AND tracked_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """)
                stats = cursor.fetchone()

                if stats and stats['total_trades'] and stats['total_trades'] > 0:
                    win_rate = stats['wins'] / stats['total_trades'] * 100
                    avg_return = float(stats['avg_return'] or 0)
                    step['baseline'] = {
                        'win_rate': round(win_rate, 2),
                        'avg_return': round(avg_return, 2),
                        'total_trades': stats['total_trades'],
                        'max_return': round(float(stats['max_return'] or 0), 2),
                        'min_return': round(float(stats['min_return'] or 0), 2),
                    }
                    print(f"  当前策略: 胜率={win_rate:.1f}%, 平均收益={avg_return:.2f}%, "
                          f"样本={stats['total_trades']}笔")
                else:
                    step['baseline'] = {'win_rate': 0, 'avg_return': 0, 'total_trades': 0}
                    print(f"  暂无实盘跟踪数据（系统运行不足30天）")
        finally:
            conn.close()

        step['status'] = 'done'

    except Exception as e:
        step['status'] = 'error'
        step['error'] = str(e)
        step['baseline'] = {'win_rate': 0, 'avg_return': 0, 'total_trades': 0}
        print(f"  ⚠️ 获取基线失败: {e}")

    return step


def _step_run_evolution():
    """Step 3: 运行遗传算法回测进化"""
    print(f"\n--- Step 3: 运行遗传算法进化 ---")
    step = {'name': 'evolution', 'status': 'running'}

    try:
        from app.learning.backtester import run_evolution, MARKET_PERIODS, save_backtest_result

        # 使用所有历史时期进行回测
        result = run_evolution(
            periods=MARKET_PERIODS,
            generations=30,           # 30代进化
            target_win_rate=65.0,     # 目标胜率65%
            target_avg_return=5.0,    # 目标T+10平均收益5%
        )

        step['evolution_result'] = result
        step['status'] = 'done'

        # 保存回测结果
        save_backtest_result(result, MARKET_PERIODS.keys())

        print(f"  ✅ 进化完成: 胜率={result['win_rate']:.1f}%, "
              f"平均收益={result['avg_return']:.2f}%, 交易数={result['total_trades']}")

    except Exception as e:
        step['status'] = 'error'
        step['error'] = str(e)
        step['evolution_result'] = None
        print(f"  ❌ 进化失败: {e}")

    return step


def _step_evaluate_and_apply(baseline_step, evolution_step):
    """Step 4: 评估进化结果，决定是否应用"""
    print(f"\n--- Step 4: 评估并应用最优策略 ---")
    step = {'name': 'apply', 'status': 'running', 'applied': False}

    evolution_result = evolution_step.get('evolution_result')
    if not evolution_result:
        step['status'] = 'skipped'
        step['reason'] = '进化未产生有效结果'
        print(f"  ⚠️ 跳过：进化未产生有效结果")
        return step

    baseline = baseline_step.get('baseline', {})
    baseline_win_rate = baseline.get('win_rate', 0)
    baseline_avg_return = baseline.get('avg_return', 0)

    evo_win_rate = evolution_result.get('win_rate', 0)
    evo_avg_return = evolution_result.get('avg_return', 0)

    # 应用条件：
    # 1. 进化结果的胜率 > 50% 且 平均收益 > 0
    # 2. 如果有实盘基线，进化结果必须优于基线
    should_apply = False
    reason = ''

    if baseline.get('total_trades', 0) < 10:
        # 实盘数据不足，只要进化结果合理就应用
        if evo_win_rate > 50 and evo_avg_return > 0:
            should_apply = True
            reason = f'实盘数据不足，进化结果合理(胜率{evo_win_rate:.1f}%>50%)'
        else:
            reason = f'进化结果不合格(胜率{evo_win_rate:.1f}%,收益{evo_avg_return:.2f}%)'
    else:
        # 有实盘基线，进化结果必须比基线好至少5个百分点
        if evo_win_rate > baseline_win_rate + 5 or evo_avg_return > baseline_avg_return + 1:
            should_apply = True
            reason = (f'优于基线(进化:{evo_win_rate:.1f}%/{evo_avg_return:.2f}% '
                      f'vs 基线:{baseline_win_rate:.1f}%/{baseline_avg_return:.2f}%)')
        else:
            reason = (f'未显著优于基线(进化:{evo_win_rate:.1f}%/{evo_avg_return:.2f}% '
                      f'vs 基线:{baseline_win_rate:.1f}%/{baseline_avg_return:.2f}%)')

    if should_apply:
        from app.learning.backtester import apply_evolution_result
        apply_evolution_result(evolution_result)
        step['applied'] = True
        step['new_weights'] = evolution_result.get('weights', {})
        step['new_params'] = evolution_result.get('params', {})
        print(f"  ✅ 已应用新策略: {reason}")
    else:
        print(f"  ℹ️ 保持当前策略: {reason}")

    step['status'] = 'done'
    step['reason'] = reason
    return step


def _step_ai_analysis():
    """Step 5: AI分析失败案例"""
    print(f"\n--- Step 5: AI分析失败案例 ---")
    step = {'name': 'ai_analysis', 'status': 'running'}

    try:
        from app.learning.optimizer import ai_suggest_rules
        from app.config import LLM_API_KEY

        if not LLM_API_KEY:
            step['status'] = 'skipped'
            step['reason'] = '未配置LLM_API_KEY'
            print(f"  ⚠️ 跳过：未配置LLM_API_KEY")
            return step

        suggestions = ai_suggest_rules()

        if suggestions:
            # 自动激活AI建议中分类为"风控"的规则（降低风险优先）
            auto_activated = _auto_activate_risk_rules(suggestions)
            step['suggestions'] = len(suggestions)
            step['auto_activated'] = auto_activated
            print(f"  ✅ AI建议 {len(suggestions)} 条规则，自动激活风控规则 {auto_activated} 条")
        else:
            step['suggestions'] = 0
            print(f"  ℹ️ 无失败案例需要分析")

        step['status'] = 'done'

    except Exception as e:
        step['status'] = 'error'
        step['error'] = str(e)
        print(f"  ⚠️ AI分析失败: {e}")

    return step


def _auto_activate_risk_rules(suggestions):
    """自动激活AI建议中的风控规则"""
    activated = 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查找最近建议的风控规则并自动激活
            cursor.execute("""
                UPDATE screening_rules
                SET status = 'active'
                WHERE source = 'ai_suggested'
                AND status = 'pending'
                AND category = '风控'
                AND created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            activated = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    return activated


def _save_evolution_log(log):
    """保存进化日志到数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 确保表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evolution_log (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    start_time DATETIME,
                    end_time DATETIME,
                    result VARCHAR(20),
                    detail JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动进化日志'
            """)
            cursor.execute(
                "INSERT INTO evolution_log (start_time, end_time, result, detail) VALUES (%s, %s, %s, %s)",
                (
                    log.get('start_time'),
                    log.get('end_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    log.get('result', 'unknown'),
                    json.dumps(log, ensure_ascii=False, default=str),
                )
            )
        conn.commit()
    except Exception as e:
        print(f"  保存进化日志失败: {e}")
    finally:
        conn.close()
