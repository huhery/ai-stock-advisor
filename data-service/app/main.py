"""AI Stock Data Service - FastAPI 入口"""
from fastapi import FastAPI, Query
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="AI Stock Data Service", version="1.0.0")
scheduler = BackgroundScheduler()


@app.on_event("startup")
def startup():
    from app.crawler.policy_crawler import crawl_all_sources
    from app.learning.tracker import track_recommendations
    from app.learning.optimizer import weekly_optimize, ai_suggest_rules
    from app.screening.engine import run_screening
    from app.screening.signals import check_all_holdings, check_pending_buys
    from app.learning.auto_evolution import run_weekly_evolution

    # === 每日任务 ===
    # 每日 9:30 爬取新闻（开盘后一次）
    scheduler.add_job(crawl_all_sources, 'cron', hour=9, minute=30, id='crawl_news_am')
    # 每日 15:35 自动选股
    scheduler.add_job(run_screening, 'cron', hour=15, minute=35, id='daily_screening')
    # 每日 15:45 检查待买入是否成交（pending -> holding）
    scheduler.add_job(check_pending_buys, 'cron', hour=15, minute=45, id='check_pending')
    # 每日 15:50 检查卖出信号（只对已成交持仓）
    scheduler.add_job(check_all_holdings, 'cron', hour=15, minute=50, id='check_sell')
    # 每日 16:00 跟踪推荐表现
    scheduler.add_job(track_recommendations, 'cron', hour=16, minute=0, id='daily_tracking')

    # === 每周自动进化（核心） ===
    # 每周六 2:00 执行完整进化流程（回测+优化+应用+AI分析）
    scheduler.add_job(run_weekly_evolution, 'cron', day_of_week='sat', hour=2, id='weekly_evolution')
    # 每周日 20:00 基于实盘数据微调权重
    scheduler.add_job(weekly_optimize, 'cron', day_of_week='sun', hour=20, id='weekly_optimize')
    # 每周日 20:30 AI 建议新规则
    scheduler.add_job(ai_suggest_rules, 'cron', day_of_week='sun', hour=20, minute=30, id='ai_suggest')

    # === 微淼财务自由模块进化 ===
    from app.weimu.evolution import run_weimu_evolution
    # 每周三 3:00 执行财务自由模块自动进化（分析政策+行情+调整参数）
    scheduler.add_job(run_weimu_evolution, 'cron', day_of_week='wed', hour=3, id='weimu_evolution')

    scheduler.start()
    print("定时任务已启动:")
    print("  每日: 9:30新闻 | 15:35选股 | 15:50卖出检查 | 16:00跟踪")
    print("  每周: 周六2:00自动进化 | 周日20:00微调权重 | 周日20:30 AI建议")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()


@app.get("/health")
def health():
    return {"status": "ok"}


# ===== 资讯相关 API =====

@app.get("/api/news/latest")
def get_latest_news(limit: int = Query(default=20, ge=1, le=100)):
    """获取最新资讯列表"""
    from app.crawler.policy_crawler import get_latest_news
    return {"code": 0, "data": get_latest_news(limit)}


@app.get("/api/news/search")
def search_news(keyword: str, limit: int = Query(default=20, ge=1, le=100)):
    """按关键词搜索资讯"""
    from app.crawler.policy_crawler import search_news
    return {"code": 0, "data": search_news(keyword, limit)}


@app.post("/api/news/crawl")
def trigger_crawl():
    """手动触发一次爬取"""
    from app.crawler.policy_crawler import crawl_all_sources
    crawl_all_sources()
    return {"code": 0, "message": "爬取完成"}


# ===== 选股相关 API =====

@app.get("/api/screening/today")
def get_today_screening():
    """获取今日选股结果"""
    from app.screening.engine import get_today_recommendations
    return {"code": 0, "data": get_today_recommendations()}


@app.get("/api/screening/history")
def get_history_screening(date: str):
    """获取历史选股结果"""
    from app.screening.engine import get_history_recommendations
    return {"code": 0, "data": get_history_recommendations(date)}


@app.get("/api/screening/dates")
def get_screening_dates():
    """获取所有有选股记录的日期列表"""
    from app.screening.engine import get_available_dates
    return {"code": 0, "data": get_available_dates()}


@app.post("/api/screening/run")
def trigger_screening():
    """手动触发选股"""
    from app.screening.engine import run_screening
    results = run_screening()
    return {"code": 0, "message": f"选股完成，推荐 {len(results) if results else 0} 只"}


@app.get("/api/screening/rules")
def get_screening_rules():
    """获取当前筛选规则"""
    from app.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM screening_rules ORDER BY category, weight DESC")
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return {"code": 0, "data": results}
    finally:
        conn.close()


# ===== 跟踪与学习 API =====

@app.get("/api/tracking/performance")
def get_performance():
    """获取推荐表现统计"""
    from app.learning.tracker import get_performance_summary
    return {"code": 0, "data": get_performance_summary()}


@app.post("/api/tracking/run")
def trigger_tracking():
    """手动触发跟踪"""
    from app.learning.tracker import track_recommendations
    track_recommendations()
    return {"code": 0, "message": "跟踪完成"}


@app.get("/api/learning/suggestions")
def get_suggestions():
    """获取 AI 建议的新规则"""
    from app.learning.optimizer import get_pending_suggestions
    return {"code": 0, "data": get_pending_suggestions()}


@app.post("/api/learning/approve-rule")
def approve_rule(rule_id: int):
    """用户确认新规则"""
    from app.learning.optimizer import approve_rule as do_approve
    do_approve(rule_id)
    return {"code": 0, "message": "规则已激活"}


@app.post("/api/learning/reject-rule")
def reject_rule(rule_id: int):
    """用户拒绝规则"""
    from app.learning.optimizer import reject_rule as do_reject
    do_reject(rule_id)
    return {"code": 0, "message": "规则已拒绝"}


@app.post("/api/learning/optimize")
def trigger_optimize():
    """手动触发规则优化"""
    from app.learning.optimizer import weekly_optimize
    weekly_optimize()
    return {"code": 0, "message": "优化完成"}


@app.post("/api/learning/ai-suggest")
def trigger_ai_suggest():
    """手动触发 AI 规则建议"""
    from app.learning.optimizer import ai_suggest_rules
    suggestions = ai_suggest_rules()
    return {"code": 0, "data": suggestions}


@app.post("/api/signals/check-sell")
def trigger_check_sell():
    """手动触发卖出信号检查（先检查待买入成交，再检查卖出）"""
    from app.screening.signals import check_all_holdings, check_pending_buys
    check_pending_buys()
    check_all_holdings()
    return {"code": 0, "message": "买入成交与卖出信号检查完成"}


# ===== 自动进化 API =====

@app.post("/api/evolution/run")
def trigger_evolution():
    """手动触发一次完整的自动进化流程"""
    from app.learning.auto_evolution import run_weekly_evolution
    import threading

    if hasattr(app, '_evolution_running') and app._evolution_running:
        return {"code": -1, "message": "已有进化任务在运行中"}

    def run_task():
        app._evolution_running = True
        try:
            run_weekly_evolution()
        finally:
            app._evolution_running = False

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()
    return {"code": 0, "message": "自动进化已启动，后台运行中"}


@app.get("/api/evolution/log")
def get_evolution_log():
    """查看进化日志"""
    from app.db import get_connection
    import json as json_lib
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM evolution_log
                             ORDER BY created_at DESC LIMIT 10""")
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('start_time'):
                    r['start_time'] = r['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('end_time'):
                    r['end_time'] = r['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('detail') and isinstance(r['detail'], str):
                    r['detail'] = json_lib.loads(r['detail'])
            return {"code": 0, "data": results}
    except Exception:
        return {"code": 0, "data": []}
    finally:
        conn.close()


# ===== 回测进化 API =====

@app.post("/api/backtest/run")
def run_backtest(
    generations: int = 20,
    target_win_rate: float = 65.0,
    target_avg_return: float = 5.0,
    periods: str = None
):
    """启动回测进化优化（异步执行）

    立即返回任务ID，后台执行进化。通过 /api/backtest/status 查询进度。
    """
    from app.learning.backtester import run_evolution, MARKET_PERIODS, save_backtest_result
    import threading

    # 解析时期
    selected_periods = MARKET_PERIODS
    if periods:
        period_names = [p.strip() for p in periods.split(',')]
        selected_periods = {k: v for k, v in MARKET_PERIODS.items() if k in period_names}
        if not selected_periods:
            return {"code": -1, "message": f"无效的时期名，可选: {list(MARKET_PERIODS.keys())}"}

    # 检查是否已有任务在运行
    if hasattr(app, '_backtest_running') and app._backtest_running:
        return {"code": -1, "message": "已有回测任务在运行中，请等待完成"}

    # 后台线程执行
    def run_task():
        app._backtest_running = True
        app._backtest_progress = {"generation": 0, "total": generations, "status": "running"}
        try:
            def on_progress(gen, best):
                app._backtest_progress = {
                    "generation": gen,
                    "total": generations,
                    "status": "running",
                    "current_best": best
                }

            result = run_evolution(
                periods=selected_periods,
                generations=generations,
                target_win_rate=target_win_rate,
                target_avg_return=target_avg_return,
                callback=on_progress
            )
            save_backtest_result(result, selected_periods.keys())
            app._backtest_progress = {
                "generation": generations,
                "total": generations,
                "status": "completed",
                "result": result
            }
        except Exception as e:
            app._backtest_progress = {
                "status": "failed",
                "error": str(e)
            }
        finally:
            app._backtest_running = False

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return {"code": 0, "message": "回测任务已启动，请通过 /api/backtest/status 查询进度"}


@app.get("/api/backtest/status")
def get_backtest_status():
    """查询回测进度"""
    if hasattr(app, '_backtest_progress'):
        return {"code": 0, "data": app._backtest_progress}
    return {"code": 0, "data": {"status": "idle", "message": "没有正在运行的回测任务"}}


@app.post("/api/backtest/apply")
def apply_backtest(backtest_id: int = None):
    """将回测最优结果应用到当前规则

    Args:
        backtest_id: 指定回测记录 ID，为空则取最新
    """
    from app.learning.backtester import apply_evolution_result
    from app.db import get_connection
    import json

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if backtest_id:
                cursor.execute("SELECT * FROM backtest_history WHERE id = %s", (backtest_id,))
            else:
                cursor.execute("SELECT * FROM backtest_history ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {"code": -1, "message": "无回测记录"}

            result = {
                'weights': json.loads(row['best_weights']) if isinstance(row['best_weights'], str)
                           else row['best_weights'],
                'params': json.loads(row['best_params']) if isinstance(row['best_params'], str)
                          else row['best_params'],
            }
            apply_evolution_result(result)

            # 标记为已应用
            cursor.execute("UPDATE backtest_history SET applied = 1 WHERE id = %s", (row['id'],))
            conn.commit()

            return {"code": 0, "message": "已应用最优权重", "data": result}
    finally:
        conn.close()


@app.get("/api/backtest/history")
def get_backtest_history():
    """获取回测历史记录"""
    from app.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM backtest_history ORDER BY created_at DESC LIMIT 20")
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return {"code": 0, "data": results}
    finally:
        conn.close()


@app.get("/api/backtest/periods")
def get_available_periods():
    """获取可用的回测时期"""
    from app.learning.backtester import MARKET_PERIODS
    return {"code": 0, "data": MARKET_PERIODS}


# ===== 数据缓存 API =====

@app.post("/api/cache/prefetch")
def prefetch_cache(start_date: str = "2020-01-01", end_date: str = "2026-06-01"):
    """预缓存股票K线数据到 MySQL

    在本地网络环境好的机器上调用此接口，将历史数据灌入数据库。
    之后 Docker 内的回测直接读缓存，不依赖网络。

    示例：curl -X POST "http://localhost:8001/api/cache/prefetch?start_date=2020-01-01&end_date=2026-06-01"
    """
    from app.stock_data.cache import prefetch_all
    result = prefetch_all(start_date, end_date)
    return {"code": 0, "data": result}


@app.get("/api/cache/stats")
def cache_stats():
    """查看缓存统计"""
    from app.stock_data.cache import get_cache_stats
    return {"code": 0, "data": get_cache_stats()}


# ===== 微淼财务自由选股 API =====

@app.post("/api/weimu/run")
def trigger_weimu_screening():
    """手动触发微淼财务自由选股（异步执行，耗时较长）"""
    from app.weimu.runner import run_async
    ok, message = run_async()
    code = 0 if ok else -1
    return {"code": code, "message": message}


@app.post("/api/weimu/quick")
def trigger_weimu_quick():
    """快速模式：仅对上次精选结果重算估值"""
    from app.weimu.runner import run_quick
    results = run_quick()
    return {"code": 0, "message": f"估值更新完成，{len(results)} 条记录"}


@app.get("/api/weimu/status")
def get_weimu_status():
    """查询微淼选股进度"""
    from app.weimu.runner import get_progress
    return {"code": 0, "data": get_progress()}


@app.get("/api/weimu/list")
def get_weimu_list(date: str = None):
    """获取微淼选股结果"""
    from app.db import get_connection
    from app.stock_data.market_data import get_current_price, get_stock_name

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if date:
                cursor.execute(
                    "SELECT * FROM weimu_recommendation WHERE recommend_date = %s ORDER BY score DESC",
                    (date,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM weimu_recommendation WHERE recommend_date = (SELECT MAX(recommend_date) FROM weimu_recommendation) ORDER BY score DESC"
                )
            results = cursor.fetchall()

            # 为每个结果添加实时价格信息
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('recommend_date'):
                    r['recommend_date'] = r['recommend_date'].strftime('%Y-%m-%d')

                # 股票名称为空时实时补全（腾讯/新浪接口）
                if not r.get('stock_name') or r['stock_name'].startswith('股票'):
                    name = get_stock_name(r['stock_code'])
                    r['stock_name'] = name or f"股票{r['stock_code']}"

                # 获取当前价格
                current_price = None
                try:
                    current_price = get_current_price(r['stock_code'])
                except Exception:
                    current_price = None
                r['current_price'] = current_price

                # 根据微淼标准计算建议买入/卖出价（PE有效时）
                # 注意：数据库取出的 pe 是 Decimal，current_price 是 float，
                # 需统一转 float 再运算，否则 float/Decimal 会抛 TypeError。
                r['suggest_buy_price'] = None
                r['suggest_sell_price'] = None
                try:
                    pe = float(r['pe']) if r.get('pe') is not None else 0
                    if current_price and pe > 0:
                        eps = float(current_price) / pe
                        if eps > 0:
                            # 微淼认为 PE<15 为好价格，PE>30 为高估
                            r['suggest_buy_price'] = round(eps * 15.0, 2)
                            r['suggest_sell_price'] = round(eps * 30.0, 2)
                except Exception:
                    pass

            return {"code": 0, "data": results}
    finally:
        conn.close()


@app.get("/api/weimu/history")
def get_weimu_history():
    """获取微淼选股历史日期列表"""
    from app.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT DISTINCT recommend_date
                             FROM weimu_recommendation
                             ORDER BY recommend_date DESC LIMIT 30""")
            results = cursor.fetchall()
            return {"code": 0, "data": [
                r['recommend_date'].strftime('%Y-%m-%d') for r in results if r.get('recommend_date')
            ]}
    finally:
        conn.close()


@app.get("/api/weimu/market-analysis")
def get_weimu_market_analysis():
    """获取当前市场PE估值分析

    返回深证A股当前PE值、所处区间、以及是否适合交易的建议。
    基于微淼课程的PE区间理论：
    - PE < 20: 低估，适合买入
    - PE 20-40: 合理，持有等待
    - PE > 40: 偏高，谨慎或卖出
    - PE > 60: 严重高估，应卖出
    """
    from app.weimu.valuation import get_market_analysis
    result = get_market_analysis()
    return {"code": 0, "data": result}


@app.get("/api/weimu/allocation")
def get_weimu_allocation(capital: float = 200000, expense: float = 5000):
    """获取资产配置建议

    根据投入资金和当前市场环境，基于微淼课程的3-3-1工具体系，
    给出个性化的资产配置方案。

    Args:
        capital: 总投资资金（默认20万）
        expense: 月生活支出（默认5000元，用于计算应急资金）
    """
    from app.weimu.allocation import generate_allocation_advice
    result = generate_allocation_advice(capital, expense)
    return {"code": 0, "data": result}


@app.post("/api/weimu/evolve")
def trigger_weimu_evolution():
    """手动触发微淼模块自动进化

    分析最新政策、市场行情，调整筛选参数和投资建议。
    """
    from app.weimu.evolution import run_weimu_evolution
    import threading

    def task():
        run_weimu_evolution()

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    return {"code": 0, "message": "进化任务已启动"}


@app.get("/api/weimu/advice")
def get_weimu_advice():
    """获取最新的AI进化投资建议

    包含：投资注意事项、风险警示、配置建议
    """
    from app.weimu.evolution import get_latest_advice
    return {"code": 0, "data": get_latest_advice()}


@app.get("/api/weimu/evolution-log")
def get_weimu_evolution_log():
    """获取进化历史日志"""
    from app.weimu.evolution import get_evolution_history
    return {"code": 0, "data": get_evolution_history()}


@app.get("/api/weimu/tools")
def get_weimu_tools():
    """获取所有投资工具推荐（REITs/货基/债基/逆回购）

    从公开接口实时获取各类工具的排行和利率数据，给出具体买哪个的建议。
    """
    from app.weimu.tools_screener import get_all_tools_recommendations
    return {"code": 0, "data": get_all_tools_recommendations()}
