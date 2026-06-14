"""微淼财务自由模块 — 自动进化引擎

定期根据以下信息源自动更新投资理财规则：
1. 国家最新政策（从已爬取的policy_news中分析）
2. 当前市场行情（PE水平、利率环境、市场风格）
3. 筛选结果的实际表现（选出的好公司后续走势）
4. 公开渠道的价值投资最新实践

进化输出：
- 调整筛选参数（ROE阈值、毛利率阈值等）
- 调整资产配置比例建议
- 生成最新的投资注意事项
- 记录进化日志供审查

设计原则：
- 核心价值投资理念不变（好公司+好价格+长期持有）
- 参数随市场环境微调（如利率变化导致股息率门槛变化）
- 所有自动变更可回溯、可人工覆盖
"""
import json
import re
import requests
from datetime import datetime, date
from app.db import get_connection
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.weimu.valuation import get_market_pe, get_bond_yield


# ===== 可进化的参数（当前默认值） =====
DEFAULT_PARAMS = {
    # 海选
    'preliminary_roe_min': 15.0,
    'preliminary_cash_ratio_min': 80.0,
    'preliminary_gross_margin_min': 30.0,
    'min_listing_years': 5,
    # 精选
    'fine_roe_min': 20.0,
    'fine_cash_ratio_avg_min': 100.0,
    'fine_gross_margin_min': 40.0,
    'fine_debt_ratio_max': 60.0,
    'fine_dividend_years_min': 5,
    # 估值买入
    'market_pe_buy_threshold': 20.0,
    'stock_pe_buy_threshold': 15.0,
    # 资产配置（低估时）
    'alloc_stock_ratio_low_pe': 0.50,
    'alloc_reits_ratio_low_pe': 0.15,
    'alloc_reverse_ratio_low_pe': 0.15,
}

# 参数允许的调整范围（防止AI建议过于激进）
PARAM_BOUNDS = {
    'preliminary_roe_min': (10.0, 20.0),
    'preliminary_cash_ratio_min': (60.0, 100.0),
    'preliminary_gross_margin_min': (20.0, 40.0),
    'min_listing_years': (3, 10),
    'fine_roe_min': (15.0, 30.0),
    'fine_cash_ratio_avg_min': (80.0, 150.0),
    'fine_gross_margin_min': (30.0, 60.0),
    'fine_debt_ratio_max': (40.0, 70.0),
    'fine_dividend_years_min': (3, 10),
    'market_pe_buy_threshold': (15.0, 30.0),
    'stock_pe_buy_threshold': (10.0, 25.0),
    'alloc_stock_ratio_low_pe': (0.30, 0.70),
    'alloc_reits_ratio_low_pe': (0.05, 0.25),
    'alloc_reverse_ratio_low_pe': (0.05, 0.30),
}


def run_weimu_evolution():
    """执行财务自由模块的自动进化

    流程：
    1. 收集当前市场环境数据
    2. 分析近期政策对投资策略的影响
    3. 评估上次筛选结果的表现
    4. 调用LLM综合分析，给出参数调整建议
    5. 验证建议合理性，应用通过的调整
    6. 生成进化报告
    """
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] 🧬 微淼财务自由模块 — 自动进化开始")
    print(f"{'='*60}")

    log = {
        'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'steps': [],
        'result': 'pending',
    }

    try:
        # Step 1: 收集市场环境
        market_context = _collect_market_context()
        log['steps'].append({'name': 'market_context', 'data': market_context})
        print(f"  ✅ Step 1: 市场环境收集完成")

        # Step 2: 收集政策影响
        policy_context = _collect_policy_context()
        log['steps'].append({'name': 'policy_context', 'count': len(policy_context)})
        print(f"  ✅ Step 2: 收集到 {len(policy_context)} 条近期政策")

        # Step 3: 评估上次结果
        performance = _evaluate_past_performance()
        log['steps'].append({'name': 'performance', 'data': performance})
        print(f"  ✅ Step 3: 历史表现评估完成")

        # Step 4: LLM综合分析
        current_params = _get_current_params()
        suggestions = _llm_analyze_and_suggest(
            market_context, policy_context, performance, current_params
        )
        log['steps'].append({'name': 'llm_suggestions', 'data': suggestions})
        print(f"  ✅ Step 4: LLM分析完成")

        # Step 5: 验证并应用
        applied = _validate_and_apply(suggestions)
        log['steps'].append({'name': 'applied', 'data': applied})
        print(f"  ✅ Step 5: 应用了 {len(applied)} 项调整")

        log['result'] = 'success'

    except Exception as e:
        log['result'] = 'error'
        log['error'] = str(e)
        print(f"  ❌ 进化异常: {e}")

    log['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _save_evolution_log(log)

    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] 🧬 微淼财务自由进化完成: {log['result']}")
    print(f"{'='*60}\n")

    return log


def _collect_market_context():
    """收集当前市场环境数据"""
    market_pe = get_market_pe()
    bond_yield = get_bond_yield()

    return {
        'market_pe': market_pe,
        'bond_yield': bond_yield,
        'date': date.today().isoformat(),
        'pe_zone': _pe_zone(market_pe),
        'rate_environment': 'low' if bond_yield < 2.5 else 'normal' if bond_yield < 4.0 else 'high',
    }


def _pe_zone(pe):
    if pe < 15: return '极度低估'
    if pe < 20: return '低估'
    if pe < 30: return '合理偏低'
    if pe < 40: return '合理'
    if pe < 55: return '偏高'
    return '严重高估'


def _collect_policy_context():
    """从已爬取的政策新闻中提取与投资相关的最新政策"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT title, source, keywords, related_sectors, category
                FROM policy_news
                WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
                AND (keywords IS NOT NULL OR related_sectors IS NOT NULL)
                ORDER BY created_at DESC
                LIMIT 30
            """)
            results = cursor.fetchall()
            return results
    except Exception:
        return []
    finally:
        conn.close()


def _evaluate_past_performance():
    """评估上次微淼选股结果的表现"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查看有多少历史记录
            cursor.execute("SELECT COUNT(*) as cnt FROM weimu_recommendation")
            count = cursor.fetchone()['cnt']

            # 简单统计：上次推荐的股票当前PE是否处于合理区间
            cursor.execute("""
                SELECT stock_code, pe, valuation, score, recommend_date
                FROM weimu_recommendation
                WHERE recommend_date = (SELECT MAX(recommend_date) FROM weimu_recommendation)
                ORDER BY score DESC
            """)
            last_results = cursor.fetchall()

            return {
                'total_historical': count,
                'last_batch_count': len(last_results),
                'last_batch_buy': sum(1 for r in last_results if r.get('valuation') == 'buy'),
                'last_batch_hold': sum(1 for r in last_results if r.get('valuation') == 'hold'),
                'last_batch_wait': sum(1 for r in last_results if r.get('valuation') == 'wait'),
            }
    except Exception:
        return {'total_historical': 0, 'last_batch_count': 0}
    finally:
        conn.close()


def _get_current_params():
    """获取当前参数（从数据库或默认值）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT params FROM weimu_evolution_params
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row and row.get('params'):
                return json.loads(row['params']) if isinstance(row['params'], str) else row['params']
    except Exception:
        pass
    finally:
        conn.close()

    return DEFAULT_PARAMS.copy()


def _llm_analyze_and_suggest(market_context, policy_context, performance, current_params):
    """调用LLM分析所有信息，给出参数调整建议"""
    if not LLM_API_KEY:
        print("  ⚠️ 未配置LLM_API_KEY，使用规则化进化")
        return _rule_based_suggestions(market_context, current_params)

    # 组装政策摘要
    policy_summary = ""
    for p in policy_context[:15]:
        title = p.get('title', '')
        keywords = p.get('keywords', '')
        sectors = p.get('related_sectors', '')
        policy_summary += f"- [{p.get('source', '')}] {title}"
        if keywords:
            policy_summary += f" (关键词: {keywords})"
        if sectors:
            policy_summary += f" (利好: {sectors})"
        policy_summary += "\n"

    prompt = f"""你是一位资深A股价值投资研究员，精通微淼商学院的财务自由投资方法论。

当前市场环境：
- 深证A股PE: {market_context['market_pe']} ({market_context['pe_zone']})
- 10年国债收益率: {market_context['bond_yield']}%
- 利率环境: {market_context['rate_environment']}
- 日期: {market_context['date']}

近期重要政策/新闻：
{policy_summary if policy_summary else '暂无近期重要政策'}

上次筛选表现：
- 精选好公司数: {performance.get('last_batch_count', 0)}
- 可买入: {performance.get('last_batch_buy', 0)} 只
- 等待中: {performance.get('last_batch_wait', 0)} 只

当前筛选参数：
{json.dumps(current_params, indent=2, ensure_ascii=False)}

请基于以下原则分析并给出调整建议：
1. 核心价值投资理念不变：好公司+好价格+长期持有
2. 参数调整要有明确理由，不能无故放松标准
3. 低利率环境下股息率门槛可适当降低
4. 政策方向性变化需要反映到筛选逻辑中
5. 退市新规趋严时应提高安全标准

请严格按以下JSON格式输出（只输出JSON，不要其他内容）：
{{
  "param_adjustments": [
    {{"param": "参数名", "old_value": 旧值, "new_value": 新值, "reason": "调整原因"}}
  ],
  "investment_notes": [
    "当前市场的投资注意事项1",
    "当前市场的投资注意事项2"
  ],
  "allocation_advice": "对当前资产配置的额外建议",
  "risk_warnings": [
    "当前需要警惕的风险1"
  ]
}}
"""

    try:
        headers = {
            'Authorization': f'Bearer {LLM_API_KEY}',
            'Content-Type': 'application/json'
        }
        body = {
            'model': LLM_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.3,
        }
        resp = requests.post(
            f'{LLM_BASE_URL}/chat/completions',
            headers=headers,
            json=body,
            timeout=60
        )
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        print(f"  LLM返回状态码: {resp.status_code}")
    except Exception as e:
        print(f"  LLM调用失败: {e}")

    # 降级到规则化进化
    return _rule_based_suggestions(market_context, current_params)


def _rule_based_suggestions(market_context, current_params):
    """无LLM时的规则化进化逻辑

    基于确定性规则自动调整参数：
    - 利率下降 → 降低股息率买入门槛
    - 市场PE下降到极低 → 可放宽PE买入门槛
    - 退市频率增加 → 提高安全指标要求
    """
    adjustments = []
    notes = []
    warnings = []

    market_pe = market_context['market_pe']
    bond_yield = market_context['bond_yield']

    # 规则1：低利率环境调整
    if bond_yield < 2.0:
        if current_params.get('stock_pe_buy_threshold', 15) < 18:
            adjustments.append({
                'param': 'stock_pe_buy_threshold',
                'old_value': current_params.get('stock_pe_buy_threshold', 15),
                'new_value': 18,
                'reason': f'国债收益率仅{bond_yield}%（历史低位），适当放宽PE买入门槛'
            })
        notes.append(f'当前10年国债收益率仅{bond_yield}%，处于历史低位，高股息股的吸引力显著增强')

    # 规则2：市场极度低估时放宽
    if market_pe < 15:
        notes.append(f'市场PE={market_pe}，极度低估，应大胆买入好公司，这是难得的历史机遇')
        if current_params.get('alloc_stock_ratio_low_pe', 0.5) < 0.6:
            adjustments.append({
                'param': 'alloc_stock_ratio_low_pe',
                'old_value': current_params.get('alloc_stock_ratio_low_pe', 0.5),
                'new_value': 0.60,
                'reason': '市场极度低估，应加大股票配置比例'
            })

    # 规则3：市场偏高时收紧
    if market_pe > 40:
        warnings.append('市场PE偏高，不适合买入新股票，应考虑逐步减仓')
        if current_params.get('alloc_stock_ratio_low_pe', 0.5) > 0.3:
            adjustments.append({
                'param': 'alloc_stock_ratio_low_pe',
                'old_value': current_params.get('alloc_stock_ratio_low_pe', 0.5),
                'new_value': 0.30,
                'reason': '市场偏高，降低股票配置建议比例'
            })

    # 规则4：退市潮警示（2024-2026 A股退市加速）
    warnings.append('注意：2024-2026年A股退市提速，务必避开市值<50亿、连续亏损的公司')
    notes.append('国九条(2024)要求上市公司加大分红力度，连续分红的好公司将持续受益')

    return {
        'param_adjustments': adjustments,
        'investment_notes': notes,
        'allocation_advice': '当前低利率环境下，高股息策略是实现财务自由的核心路径',
        'risk_warnings': warnings,
    }


def _validate_and_apply(suggestions):
    """验证LLM建议的合理性，应用通过的调整"""
    if not suggestions:
        return []

    applied = []
    adjustments = suggestions.get('param_adjustments', [])

    current_params = _get_current_params()

    for adj in adjustments:
        param = adj.get('param', '')
        new_value = adj.get('new_value')

        if param not in PARAM_BOUNDS:
            continue  # 未知参数，跳过

        bounds = PARAM_BOUNDS[param]
        # 确保新值在允许范围内
        if isinstance(new_value, (int, float)):
            new_value = max(bounds[0], min(bounds[1], new_value))
            current_params[param] = new_value
            applied.append({
                'param': param,
                'new_value': new_value,
                'reason': adj.get('reason', ''),
            })

    # 保存更新后的参数
    if applied:
        _save_params(current_params)

    # 保存投资注意事项
    notes = suggestions.get('investment_notes', [])
    warnings = suggestions.get('risk_warnings', [])
    alloc_advice = suggestions.get('allocation_advice', '')
    if notes or warnings or alloc_advice:
        _save_advice(notes, warnings, alloc_advice)

    return applied


def _save_params(params):
    """保存进化后的参数"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weimu_evolution_params (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    params JSON NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute(
                "INSERT INTO weimu_evolution_params (params) VALUES (%s)",
                (json.dumps(params, ensure_ascii=False),)
            )
        conn.commit()
    except Exception as e:
        print(f"  保存参数失败: {e}")
    finally:
        conn.close()


def _save_advice(notes, warnings, alloc_advice):
    """保存最新的投资建议"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weimu_evolution_advice (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    investment_notes JSON,
                    risk_warnings JSON,
                    allocation_advice TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute(
                "INSERT INTO weimu_evolution_advice (investment_notes, risk_warnings, allocation_advice) VALUES (%s, %s, %s)",
                (
                    json.dumps(notes, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    alloc_advice,
                )
            )
        conn.commit()
    except Exception as e:
        print(f"  保存建议失败: {e}")
    finally:
        conn.close()


def _save_evolution_log(log):
    """保存进化日志"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weimu_evolution_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    start_time DATETIME,
                    end_time DATETIME,
                    result VARCHAR(20),
                    detail JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute(
                "INSERT INTO weimu_evolution_log (start_time, end_time, result, detail) VALUES (%s, %s, %s, %s)",
                (
                    log.get('start_time'),
                    log.get('end_time'),
                    log.get('result'),
                    json.dumps(log, ensure_ascii=False, default=str),
                )
            )
        conn.commit()
    except Exception as e:
        print(f"  保存进化日志失败: {e}")
    finally:
        conn.close()


def get_latest_advice():
    """获取最新的进化投资建议（供API和前端展示）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM weimu_evolution_advice
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {
                    'investment_notes': json.loads(row['investment_notes']) if isinstance(row['investment_notes'], str) else row['investment_notes'],
                    'risk_warnings': json.loads(row['risk_warnings']) if isinstance(row['risk_warnings'], str) else row['risk_warnings'],
                    'allocation_advice': row.get('allocation_advice', ''),
                    'updated_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row.get('created_at') else None,
                }
    except Exception:
        pass
    finally:
        conn.close()

    # 默认建议
    return {
        'investment_notes': [
            '坚持价值投资：好公司 + 好价格 + 长期持有',
            '不预测，只计算：买卖依据取决于PE和股息率的计算结果',
            '国九条(2024)后连续分红的公司将持续受益于政策红利',
        ],
        'risk_warnings': [
            '2024-2026年A股退市加速，务必避开市值<50亿的小公司',
            '注册制后新股"化妆"更普遍，上市不足5年的公司需要格外谨慎',
        ],
        'allocation_advice': '低利率环境下，高股息策略是实现财务自由的核心路径',
        'updated_at': None,
    }


def get_evolution_history():
    """获取进化历史日志"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, start_time, end_time, result, detail
                FROM weimu_evolution_log
                ORDER BY created_at DESC LIMIT 10
            """)
            results = cursor.fetchall()
            for r in results:
                if r.get('start_time'):
                    r['start_time'] = r['start_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('end_time'):
                    r['end_time'] = r['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('detail') and isinstance(r['detail'], str):
                    r['detail'] = json.loads(r['detail'])
            return results
    except Exception:
        return []
    finally:
        conn.close()
