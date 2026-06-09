"""自学习优化模块

每周自动调整规则权重 + AI 辅助分析失败案例。
"""
import json
import requests
from datetime import datetime
from app.db import get_connection
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def weekly_optimize():
    """每周日执行：规则权重自动调整

    逻辑：
    1. 统计每条规则参与推荐时的胜率
    2. 胜率 > 60%：权重 +10%
    3. 胜率 < 40%：权重 -20%
    4. 连续 4 周胜率 < 30%：标记待淘汰
    """
    print(f"[{datetime.now()}] 开始每周规则优化...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取所有活跃规则
            cursor.execute("SELECT * FROM screening_rules WHERE status = 'active'")
            rules = cursor.fetchall()

            for rule in rules:
                rule_name = rule['name']
                # 统计该规则得分 > 50 的推荐中，T+5 盈利的比例
                sql = """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN t.change_pct > 0 THEN 1 ELSE 0 END) as wins
                    FROM stock_recommendation r
                    JOIN recommendation_tracking t ON t.recommendation_id = r.id
                    WHERE t.days_after = 5
                    AND r.recommend_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                    AND JSON_EXTRACT(r.rule_scores, %s) IS NOT NULL
                """
                json_path = f'$."{rule_name}".score'
                cursor.execute(sql, (json_path,))
                stats = cursor.fetchone()

                if stats and stats['total'] >= 5:  # 至少 5 个样本
                    win_rate = stats['wins'] / stats['total'] * 100
                    new_weight = float(rule['weight'])

                    if win_rate > 60:
                        new_weight = min(new_weight * 1.10, 3.0)  # 上限 3.0
                    elif win_rate < 40:
                        new_weight = max(new_weight * 0.80, 0.1)  # 下限 0.1

                    # 更新规则
                    update_sql = """UPDATE screening_rules
                                    SET weight = %s, win_rate = %s, total_used = total_used + %s
                                    WHERE id = %s"""
                    cursor.execute(update_sql, (
                        round(new_weight, 2), round(win_rate, 2),
                        stats['total'], rule['id']
                    ))

                    # 连续低胜率标记
                    if win_rate < 30 and float(rule['win_rate']) < 30:
                        cursor.execute(
                            "UPDATE screening_rules SET status = 'low_weight' WHERE id = %s",
                            (rule['id'],)
                        )

            conn.commit()
    finally:
        conn.close()

    print(f"[{datetime.now()}] 规则优化完成")


def ai_suggest_rules():
    """AI 分析失败案例，建议新规则

    流程：
    1. 查询本周亏损 > 5% 的推荐
    2. 组装 Prompt 发送给大模型
    3. 解析 AI 返回的建议
    4. 存入待审批
    """
    print(f"[{datetime.now()}] 开始 AI 规则建议分析...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询近期失败案例
            sql = """
                SELECT r.stock_code, r.stock_name, r.sector, r.reason, r.rule_scores,
                       t.change_pct, t.days_after
                FROM stock_recommendation r
                JOIN recommendation_tracking t ON t.recommendation_id = r.id
                WHERE t.days_after = 5
                AND t.change_pct < -5
                AND r.recommend_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                ORDER BY t.change_pct ASC
                LIMIT 10
            """
            cursor.execute(sql)
            failures = cursor.fetchall()
    finally:
        conn.close()

    if not failures:
        print("  本周无明显失败案例，跳过")
        return []

    # 组装 Prompt
    failure_text = ""
    for f in failures:
        failure_text += f"- {f['stock_name']}({f['stock_code']})，板块：{f['sector']}，"
        failure_text += f"T+5 跌幅：{f['change_pct']}%，筛选理由：{f['reason']}\n"

    prompt = f"""你是一位资深量化研究员。以下是本周选股模型推荐后亏损超过5%的股票：

{failure_text}

请分析：
1. 这些失败案例有什么共同特征？
2. 现有筛选逻辑可能遗漏了什么风险因素？
3. 建议新增什么筛选规则来避免类似失败？

请用以下 JSON 格式输出建议的新规则（最多3条）：
[
  {{"name": "规则名称", "description": "规则描述和判断逻辑", "category": "分类(政策/技术/基本面/资金/风控)"}}
]
"""

    # 调用大模型
    suggestions = call_llm_for_suggestions(prompt)
    if suggestions:
        save_suggestions(suggestions)

    return suggestions


def call_llm_for_suggestions(prompt):
    """调用大模型获取规则建议"""
    if not LLM_API_KEY:
        print("  未配置 LLM API Key，跳过 AI 建议")
        return []

    try:
        headers = {
            'Authorization': f'Bearer {LLM_API_KEY}',
            'Content-Type': 'application/json'
        }
        body = {
            'model': LLM_MODEL,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7
        }
        resp = requests.post(
            f'{LLM_BASE_URL}/chat/completions',
            headers=headers,
            json=body,
            timeout=60
        )
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        print(f"  LLM 调用返回状态码: {resp.status_code}")
    except Exception as e:
        print(f"  AI 建议调用失败: {e}")
    return []


def save_suggestions(suggestions):
    """保存 AI 建议的规则到数据库（status=pending）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for s in suggestions:
                sql = """INSERT INTO screening_rules
                         (name, description, category, weight, status, source)
                         VALUES (%s, %s, %s, 1.00, 'pending', 'ai_suggested')"""
                cursor.execute(sql, (
                    s.get('name', '未命名规则'),
                    s.get('description', ''),
                    s.get('category', '风控')
                ))
        conn.commit()
        print(f"  保存 {len(suggestions)} 条 AI 建议规则")
    finally:
        conn.close()


def get_pending_suggestions():
    """获取待审批的 AI 建议规则"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT * FROM screening_rules
                     WHERE source = 'ai_suggested' AND status = 'pending'
                     ORDER BY created_at DESC"""
            cursor.execute(sql)
            results = cursor.fetchall()
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()


def approve_rule(rule_id):
    """用户确认规则，激活"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE screening_rules SET status = 'active' WHERE id = %s AND status = 'pending'"
            cursor.execute(sql, (rule_id,))
        conn.commit()
    finally:
        conn.close()


def reject_rule(rule_id):
    """用户拒绝规则"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE screening_rules SET status = 'disabled' WHERE id = %s AND status = 'pending'"
            cursor.execute(sql, (rule_id,))
        conn.commit()
    finally:
        conn.close()
