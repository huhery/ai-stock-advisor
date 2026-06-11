"""历史回测 + 进化优化模块

通过跑历史数据来验证和优化选股策略：
1. 选取牛市/熊市/震荡市不同时期的历史数据
2. 用当前规则和权重模拟选股
3. 计算模拟收益率
4. 通过遗传算法进化规则权重和参数，找到最优组合
5. 反复迭代直到收益率达到目标
"""
import random
import copy
import time
from datetime import datetime, date, timedelta
from app.db import get_connection
from app.stock_data.market_data import get_daily_kline, calculate_ma, calculate_macd
import akshare as ak


# ===== 历史时期定义 =====
MARKET_PERIODS = {
    '牛市_2020': {'start': '2020-03-01', 'end': '2020-07-31', 'type': 'bull'},
    '牛市_2024': {'start': '2024-09-15', 'end': '2024-11-30', 'type': 'bull'},
    '熊市_2022': {'start': '2022-01-01', 'end': '2022-04-30', 'type': 'bear'},
    '熊市_2023': {'start': '2023-07-01', 'end': '2023-10-31', 'type': 'bear'},
    '震荡_2021': {'start': '2021-03-01', 'end': '2021-08-31', 'type': 'sideways'},
    '震荡_2025': {'start': '2025-01-01', 'end': '2025-05-31', 'type': 'sideways'},
}

# 进化算法参数
POPULATION_SIZE = 8        # 种群大小（减小加速）
MAX_GENERATIONS = 50       # 最大迭代代数
MUTATION_RATE = 0.3        # 变异率
CROSSOVER_RATE = 0.7       # 交叉率
TARGET_WIN_RATE = 65.0     # 目标胜率 (%)
TARGET_AVG_RETURN = 5.0    # 目标平均收益率 (%)


class Individual:
    """个体：一组规则权重和参数"""

    def __init__(self, weights=None, params=None):
        self.weights = weights or {}
        self.params = params or {
            'take_profit_pct': 10.0,
            'stop_loss_pct': 5.0,
            'max_hold_days': 10,
            'min_score_threshold': 50,
        }
        self.fitness = 0
        self.win_rate = 0
        self.avg_return = 0
        self.total_trades = 0

    def to_dict(self):
        return {
            'weights': self.weights,
            'params': self.params,
            'fitness': round(self.fitness, 4),
            'win_rate': round(self.win_rate, 2),
            'avg_return': round(self.avg_return, 2),
            'total_trades': self.total_trades,
        }


def get_current_rules():
    """从数据库获取当前规则名和权重"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, weight, category FROM screening_rules WHERE status = 'active'")
            rules = cursor.fetchall()
            return {r['name']: float(r['weight']) for r in rules}
    finally:
        conn.close()


def get_historical_stocks(period_start, period_end, limit=200):
    """获取历史时期的活跃股票列表

    直接使用预定义的股票池（沪深300成分股），不依赖网络。
    """
    from app.stock_data.stock_pool import STOCK_POOL
    result = STOCK_POOL[:limit]
    print(f"  使用股票池: {len(result)} 只股票")
    return result


def simulate_screening_on_date(stock_code, target_date, weights, params):
    """在历史某一天对某只股票模拟选股打分

    Returns:
        dict: {'score': float, 'buy_price': float} 或 None（不推荐）
    """
    try:
        from app.stock_data.cache import get_kline_cached

        # 获取目标日期前 60 天的 K 线（优先缓存）
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        start_dt = target_dt - timedelta(days=90)

        df = get_kline_cached(
            stock_code,
            start_dt.strftime('%Y-%m-%d'),
            target_dt.strftime('%Y-%m-%d')
        )
        if df is None or df.empty or len(df) < 25:
            return None

        df = calculate_ma(df)
        df = calculate_macd(df)

        # 简化打分（基于技术面规则）
        score = 0
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        # MA5 上穿 MA20
        if 'MA5' in df.columns and 'MA20' in df.columns:
            ma5_last = last.get('MA5')
            ma20_last = last.get('MA20')
            ma5_prev = prev.get('MA5')
            ma20_prev = prev.get('MA20')
            if ma5_last and ma20_last and ma5_prev and ma20_prev:
                if ma5_last > ma20_last and ma5_prev <= ma20_prev:
                    score += 85 * weights.get('MA5上穿MA20', 1.0)
                elif ma5_last > ma20_last:
                    score += 40 * weights.get('MA5上穿MA20', 1.0)

        # MACD 金叉
        if 'DIF' in df.columns and 'DEA' in df.columns:
            dif_last = last.get('DIF')
            dea_last = last.get('DEA')
            dif_prev = prev.get('DIF')
            dea_prev = prev.get('DEA')
            if dif_last and dea_last and dif_prev and dea_prev:
                if dif_last > dea_last and dif_prev <= dea_prev:
                    score += 80 * weights.get('MACD金叉', 1.0)

        # 放量突破
        if '成交量' in df.columns and len(df) >= 6:
            vol_today = last['成交量']
            vol_ma5 = df['成交量'].tail(6).iloc[:-1].mean()
            if vol_ma5 > 0 and vol_today > vol_ma5 * 2:
                score += 85 * weights.get('放量突破', 1.2)

        if score < params.get('min_score_threshold', 50):
            return None

        return {
            'score': round(score, 2),
            'buy_price': float(last['收盘']),
        }
    except Exception:
        return None


def simulate_trade(stock_code, buy_date, buy_price, params):
    """模拟一笔交易的盈亏

    从买入日开始，逐日检查是否触发卖出条件。
    Returns:
        dict: {'sell_price', 'sell_date', 'profit_pct', 'sell_reason', 'hold_days'}
    """
    take_profit_pct = params.get('take_profit_pct', 10.0)
    stop_loss_pct = params.get('stop_loss_pct', 5.0)
    max_hold_days = params.get('max_hold_days', 10)

    try:
        from app.stock_data.cache import get_kline_cached

        buy_dt = datetime.strptime(buy_date, '%Y-%m-%d')
        end_dt = buy_dt + timedelta(days=max_hold_days + 5)

        df = get_kline_cached(
            stock_code,
            buy_dt.strftime('%Y-%m-%d'),
            end_dt.strftime('%Y-%m-%d')
        )
        if df is None or df.empty or len(df) < 2:
            return None

        # 跳过买入当天，从第二天开始检查
        for i in range(1, min(len(df), max_hold_days + 1)):
            row = df.iloc[i]
            current_price = float(row['收盘'])
            high_price = float(row['最高'])
            low_price = float(row['最低'])
            change_pct = (current_price - buy_price) / buy_price * 100

            # 日内触发止盈（用最高价判断）
            if (high_price - buy_price) / buy_price * 100 >= take_profit_pct:
                sell_price = round(buy_price * (1 + take_profit_pct / 100), 2)
                return {
                    'sell_price': sell_price,
                    'profit_pct': take_profit_pct,
                    'sell_reason': '止盈',
                    'hold_days': i,
                }

            # 日内触发止损（用最低价判断）
            if (low_price - buy_price) / buy_price * 100 <= -stop_loss_pct:
                sell_price = round(buy_price * (1 - stop_loss_pct / 100), 2)
                return {
                    'sell_price': sell_price,
                    'profit_pct': -stop_loss_pct,
                    'sell_reason': '止损',
                    'hold_days': i,
                }

            # 简化的技术信号：收盘跌破买入价的 MA20
            if len(df) > 20 and i > 5:
                ma20 = df['收盘'].iloc[max(0, i-20):i].mean()
                if current_price < ma20 * 0.97:
                    return {
                        'sell_price': current_price,
                        'profit_pct': round(change_pct, 2),
                        'sell_reason': '跌破MA20',
                        'hold_days': i,
                    }

        # 到期卖出
        final_price = float(df.iloc[min(len(df)-1, max_hold_days)]['收盘'])
        final_pct = round((final_price - buy_price) / buy_price * 100, 2)
        return {
            'sell_price': final_price,
            'profit_pct': final_pct,
            'sell_reason': '到期',
            'hold_days': min(len(df)-1, max_hold_days),
        }
    except Exception:
        return None


def evaluate_individual(individual, periods=None, max_stocks_per_period=30):
    """评估个体的适应度

    在多个历史时期模拟选股和交易，计算综合收益。
    """
    if periods is None:
        periods = MARKET_PERIODS

    all_trades = []

    for period_name, period_info in periods.items():
        start = period_info['start']
        end = period_info['end']

        # 获取股票池（只获取一次，复用）
        stocks = get_historical_stocks(start, end, limit=100)
        if not stocks:
            print(f"  {period_name}: 无候选股票，跳过")
            continue

        # 模拟选股（每个时期取几个交易日）
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        total_days = (end_dt - start_dt).days

        period_trades = 0
        # 每隔 14 天选一次股（减少查询次数）
        for day_offset in range(0, min(total_days, 42), 14):
            check_date = (start_dt + timedelta(days=day_offset)).strftime('%Y-%m-%d')
            # 从股票池中随机抽 8 只
            sample_size = min(8, len(stocks))
            selected = random.sample(stocks, sample_size)

            for stock_code in selected:
                result = simulate_screening_on_date(
                    stock_code, check_date, individual.weights, individual.params
                )
                if result:
                    # 模拟交易
                    trade = simulate_trade(
                        stock_code, check_date, result['buy_price'], individual.params
                    )
                    if trade:
                        all_trades.append(trade)
                        period_trades += 1

        if period_trades > 0:
            print(f"  {period_name}: {period_trades} 笔交易")

    # 计算适应度
    if not all_trades:
        individual.fitness = 0
        individual.win_rate = 0
        individual.avg_return = 0
        individual.total_trades = 0
        return

    wins = sum(1 for t in all_trades if t['profit_pct'] > 0)
    total = len(all_trades)
    avg_return = sum(t['profit_pct'] for t in all_trades) / total

    individual.win_rate = wins / total * 100
    individual.avg_return = avg_return
    individual.total_trades = total

    # 适应度 = 胜率权重 + 收益率权重 + 交易次数奖励
    individual.fitness = (
        individual.win_rate * 0.4 +
        max(individual.avg_return, -10) * 5.0 +
        min(total, 50) * 0.2  # 鼓励更多交易样本
    )


def create_random_individual(base_weights):
    """创建随机个体"""
    weights = {}
    for name, base_w in base_weights.items():
        # 在基础权重附近随机浮动 ±50%
        weights[name] = round(base_w * random.uniform(0.5, 1.5), 2)
        weights[name] = max(0.1, min(3.0, weights[name]))  # 限制范围

    params = {
        'take_profit_pct': round(random.uniform(5, 20), 1),
        'stop_loss_pct': round(random.uniform(3, 10), 1),
        'max_hold_days': random.randint(5, 15),
        'min_score_threshold': random.randint(30, 80),
    }
    return Individual(weights, params)


def crossover(parent1, parent2):
    """交叉：混合两个父代的权重和参数"""
    child_weights = {}
    for name in parent1.weights:
        if random.random() < 0.5:
            child_weights[name] = parent1.weights[name]
        else:
            child_weights[name] = parent2.weights.get(name, 1.0)

    child_params = {}
    for key in parent1.params:
        if random.random() < 0.5:
            child_params[key] = parent1.params[key]
        else:
            child_params[key] = parent2.params[key]

    return Individual(child_weights, child_params)


def mutate(individual):
    """变异：随机调整一个权重或参数"""
    if random.random() < 0.5 and individual.weights:
        # 变异权重
        name = random.choice(list(individual.weights.keys()))
        delta = random.uniform(-0.3, 0.3)
        individual.weights[name] = max(0.1, min(3.0, individual.weights[name] + delta))
    else:
        # 变异参数
        key = random.choice(list(individual.params.keys()))
        if key == 'take_profit_pct':
            individual.params[key] = round(random.uniform(5, 25), 1)
        elif key == 'stop_loss_pct':
            individual.params[key] = round(random.uniform(2, 12), 1)
        elif key == 'max_hold_days':
            individual.params[key] = random.randint(3, 20)
        elif key == 'min_score_threshold':
            individual.params[key] = random.randint(20, 90)


def run_evolution(periods=None, generations=None, target_win_rate=None,
                  target_avg_return=None, callback=None):
    """运行进化优化

    Args:
        periods: 使用的历史时期（默认全部）
        generations: 迭代代数
        target_win_rate: 目标胜率
        target_avg_return: 目标收益率
        callback: 每代结束后的回调函数

    Returns:
        dict: 最优个体信息
    """
    generations = generations or MAX_GENERATIONS
    target_win_rate = target_win_rate or TARGET_WIN_RATE
    target_avg_return = target_avg_return or TARGET_AVG_RETURN

    if periods is None:
        periods = MARKET_PERIODS

    print(f"[{datetime.now()}] 开始进化优化...")
    print(f"  种群大小: {POPULATION_SIZE}, 最大代数: {generations}")
    print(f"  目标胜率: {target_win_rate}%, 目标收益: {target_avg_return}%")
    print(f"  回测时期: {list(periods.keys())}")

    # 初始化种群
    base_weights = get_current_rules()
    population = []

    # 第一个个体使用当前权重（保留现有策略）
    current_individual = Individual(
        weights=copy.deepcopy(base_weights),
        params={
            'take_profit_pct': 10.0,
            'stop_loss_pct': 5.0,
            'max_hold_days': 10,
            'min_score_threshold': 50,
        }
    )
    population.append(current_individual)

    # 其余随机生成
    for _ in range(POPULATION_SIZE - 1):
        population.append(create_random_individual(base_weights))

    best_ever = None

    for gen in range(generations):
        # 评估所有个体
        for ind in population:
            if ind.fitness == 0:  # 未评估过
                evaluate_individual(ind, periods)

        # 按适应度排序
        population.sort(key=lambda x: x.fitness, reverse=True)
        best = population[0]

        if best_ever is None or best.fitness > best_ever.fitness:
            best_ever = copy.deepcopy(best)

        print(f"  第 {gen+1} 代: 最优适应度={best.fitness:.2f}, "
              f"胜率={best.win_rate:.1f}%, 平均收益={best.avg_return:.2f}%, "
              f"交易数={best.total_trades}")

        if callback:
            callback(gen + 1, best.to_dict())

        # 检查是否达到目标
        if best.win_rate >= target_win_rate and best.avg_return >= target_avg_return:
            print(f"  在第 {gen+1} 代达到目标！")
            break

        # 选择 + 交叉 + 变异
        # 保留前 30% 精英
        elite_count = max(2, POPULATION_SIZE // 3)
        new_population = population[:elite_count]

        # 填充剩余
        while len(new_population) < POPULATION_SIZE:
            if random.random() < CROSSOVER_RATE:
                # 锦标赛选择两个父代
                p1 = tournament_select(population)
                p2 = tournament_select(population)
                child = crossover(p1, p2)
            else:
                # 直接复制一个
                child = copy.deepcopy(random.choice(population[:elite_count]))

            if random.random() < MUTATION_RATE:
                mutate(child)

            child.fitness = 0  # 需要重新评估
            new_population.append(child)

        population = new_population

    print(f"\n[{datetime.now()}] 进化完成")
    print(f"  最优结果: 胜率={best_ever.win_rate:.1f}%, "
          f"平均收益={best_ever.avg_return:.2f}%, 交易数={best_ever.total_trades}")

    return best_ever.to_dict()


def tournament_select(population, k=3):
    """锦标赛选择"""
    candidates = random.sample(population, min(k, len(population)))
    return max(candidates, key=lambda x: x.fitness)


def apply_evolution_result(result):
    """将进化结果应用到数据库中的规则权重"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for name, weight in result['weights'].items():
                sql = "UPDATE screening_rules SET weight = %s WHERE name = %s AND status = 'active'"
                cursor.execute(sql, (round(weight, 2), name))
        conn.commit()
        print(f"  已更新 {len(result['weights'])} 条规则权重")
    finally:
        conn.close()


def get_backtest_status():
    """获取回测状态"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM backtest_history
                             ORDER BY created_at DESC LIMIT 10""")
            return cursor.fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def save_backtest_result(result, periods_used):
    """保存回测结果到数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            import json
            sql = """INSERT INTO backtest_history
                     (win_rate, avg_return, total_trades, best_weights, best_params, periods_used, created_at)
                     VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
            cursor.execute(sql, (
                result['win_rate'], result['avg_return'], result['total_trades'],
                json.dumps(result['weights'], ensure_ascii=False),
                json.dumps(result['params'], ensure_ascii=False),
                json.dumps(list(periods_used), ensure_ascii=False),
            ))
        conn.commit()
    finally:
        conn.close()
