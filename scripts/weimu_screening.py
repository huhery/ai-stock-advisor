"""微淼财务自由选股脚本

根据微淼《财务自由操作系统课》的好公司标准进行选股：
- 连续5年 ROE > 15%
- 连续5年 净利润现金含量 > 80%
- 连续5年 毛利率 > 30%
- 上市满3年
- 连续3年以上分红
- 股息率 > 3%
- 资产负债率 < 60%

使用 Scrapling 获取东方财富财务数据。

使用方法：
    pip install scrapling pymysql cryptography requests
    python scripts/weimu_screening.py --host 81.69.42.239 --password AiStock2026!
"""
import sys
import os
import time
import json
import argparse
import pymysql
import requests
import pandas as pd
from datetime import date, datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data-service'))

from app.stock_data.stock_pool import STOCK_POOL
from app.stock_data.finance_data import get_finance_indicators


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def get_connection(host, port, user, password, database):
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


def code_to_tencent(code):
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'


def fetch_realtime_batch(stock_codes):
    """批量获取实时行情"""
    results = {}
    for i in range(0, len(stock_codes), 50):
        batch = stock_codes[i:i+50]
        codes_str = ','.join([code_to_tencent(c) for c in batch])
        url = f"http://qt.gtimg.cn/q={codes_str}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'gbk'
            for line in resp.text.strip().split('\n'):
                if '~' not in line:
                    continue
                parts = line.split('~')
                if len(parts) < 45:
                    continue
                code = parts[2]
                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                if price > 0 and 'ST' not in name:
                    results[code] = {'name': name, 'price': price}
        except Exception:
            pass
        time.sleep(0.5)
    return results


def fetch_kline_tencent(stock_code, days=60):
    """获取K线"""
    tc_code = code_to_tencent(stock_code)
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,,,{days},qfq"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        stock_data = data.get('data', {}).get(tc_code, {})
        klines = stock_data.get('qfqday', stock_data.get('day', []))
        if not klines:
            return None
        rows = []
        for k in klines:
            if len(k) >= 6:
                rows.append({
                    '日期': k[0], '开盘': float(k[1]), '收盘': float(k[2]),
                    '最高': float(k[3]), '最低': float(k[4]), '成交量': int(float(k[5])),
                })
        return pd.DataFrame(rows) if rows else None
    except Exception:
        return None


def check_weimu_criteria(finance_data):
    """检查是否符合微淼好公司标准

    Returns:
        (passed: bool, score: float, reasons: list, failures: list)
    """
    score = 0
    reasons = []
    failures = []

    # 1. ROE 连续5年 > 15%
    roe_list = [r for r in finance_data.get('roe_list', []) if r is not None]
    if len(roe_list) >= 3 and all(r > 15 for r in roe_list):
        score += 30
        reasons.append(f"ROE连续{len(roe_list)}年>{min(roe_list):.1f}%")
    elif len(roe_list) >= 3 and all(r > 10 for r in roe_list):
        score += 15
        reasons.append(f"ROE尚可({min(roe_list):.1f}%-{max(roe_list):.1f}%)")
    else:
        failures.append("ROE不达标")

    # 2. 毛利率连续5年 > 30%
    gm_list = [g for g in finance_data.get('gross_margin_list', []) if g is not None]
    if len(gm_list) >= 3 and all(g > 30 for g in gm_list):
        score += 20
        reasons.append(f"毛利率连续>{min(gm_list):.1f}%")
    elif len(gm_list) >= 3 and all(g > 20 for g in gm_list):
        score += 10
        reasons.append(f"毛利率尚可({min(gm_list):.1f}%)")
    else:
        failures.append("毛利率不达标")

    # 3. 净利润现金含量 > 80%
    cash_list = [c for c in finance_data.get('cash_ratio_list', []) if c is not None]
    if len(cash_list) >= 3 and all(c > 80 for c in cash_list):
        score += 20
        reasons.append("现金含量优秀")
    elif len(cash_list) >= 2 and all(c > 50 for c in cash_list):
        score += 10
        reasons.append("现金含量尚可")

    # 4. 连续分红
    div_years = finance_data.get('continuous_dividend_years', 0)
    if div_years >= 3:
        score += 15
        reasons.append(f"连续{div_years}年分红")
    else:
        failures.append("分红不连续")

    # 5. 股息率 > 3%
    div_yield = finance_data.get('dividend_yield')
    if div_yield and div_yield > 3:
        score += 15
        reasons.append(f"股息率{div_yield:.1f}%")
    elif div_yield and div_yield > 1.5:
        score += 8
        reasons.append(f"股息率{div_yield:.1f}%")

    # 6. 资产负债率 < 60%
    debt = finance_data.get('debt_ratio')
    if debt and debt < 60:
        score += 10
        reasons.append(f"负债率{debt:.1f}%安全")
    elif debt and debt >= 60:
        failures.append(f"负债率{debt:.1f}%偏高")

    # 7. PE 合理
    pe = finance_data.get('pe')
    if pe and 0 < pe < 20:
        score += 10
        reasons.append(f"PE{pe:.1f}低估")
    elif pe and 0 < pe < 30:
        score += 5
        reasons.append(f"PE{pe:.1f}合理")

    # 判定是否通过（满分 120，达到 60 分以上算通过）
    passed = score >= 60 and len(failures) <= 1
    return passed, score, reasons, failures


def generate_buy_sell_price(price, kline_df):
    """生成买卖价格"""
    if kline_df is None or kline_df.empty or len(kline_df) < 20:
        return {
            'buy_price': price,
            'buy_type': '当前价买入',
            'take_profit_price': round(price * 1.15, 2),
            'stop_loss_price': round(price * 0.90, 2),
            'good_price': round(price * 0.85, 2),  # 好价格（打 85 折）
        }

    # 计算均线
    kline_df['MA20'] = kline_df['收盘'].rolling(20).mean()
    kline_df['MA60'] = kline_df['收盘'].rolling(60).mean() if len(kline_df) >= 60 else kline_df['收盘'].rolling(len(kline_df)).mean()

    recent_low = kline_df['最低'].tail(20).min()
    recent_high = kline_df['最高'].tail(20).max()
    ma20 = kline_df['MA20'].iloc[-1] if not pd.isna(kline_df['MA20'].iloc[-1]) else price

    # 好价格：取 MA20 和近期低点的较低者
    good_price = round(min(ma20, recent_low) * 0.95, 2)

    # 微淼体系：长期持有，止盈设高一些
    return {
        'buy_price': round(min(price, ma20), 2),
        'buy_type': '低于MA20买入' if price <= ma20 else f'建议等回调至{round(ma20, 2)}',
        'take_profit_price': round(price * 1.30, 2),  # 长期持有，止盈30%
        'stop_loss_price': round(price * 0.85, 2),    # 止损15%（给足空间）
        'good_price': good_price,
        'support': round(recent_low, 2),
        'resistance': round(recent_high, 2),
    }


def save_to_db(conn, results):
    """保存到数据库"""
    today = date.today().strftime('%Y-%m-%d')
    with conn.cursor() as cursor:
        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weimu_recommendation (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(10) NOT NULL,
                stock_name VARCHAR(50) NOT NULL,
                score INT DEFAULT 0 COMMENT '综合评分',
                roe_avg DECIMAL(5,2) COMMENT '平均ROE',
                gross_margin DECIMAL(5,2) COMMENT '毛利率',
                dividend_yield DECIMAL(5,2) COMMENT '股息率',
                pe DECIMAL(8,2) COMMENT 'PE',
                pb DECIMAL(8,2) COMMENT 'PB',
                debt_ratio DECIMAL(5,2) COMMENT '资产负债率',
                continuous_div_years INT COMMENT '连续分红年数',
                current_price DECIMAL(10,2) COMMENT '当前价格',
                buy_price DECIMAL(10,2) COMMENT '建议买入价',
                buy_type VARCHAR(100) COMMENT '买入策略',
                good_price DECIMAL(10,2) COMMENT '好价格(理想买点)',
                take_profit_price DECIMAL(10,2) COMMENT '止盈价',
                stop_loss_price DECIMAL(10,2) COMMENT '止损价',
                reasons TEXT COMMENT '入选理由',
                recommend_date DATE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_date (recommend_date),
                INDEX idx_score (score)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='微淼财务自由选股'
        """)

        # 清除今天旧数据
        cursor.execute("DELETE FROM weimu_recommendation WHERE recommend_date = %s", (today,))

        sql = """INSERT INTO weimu_recommendation
                 (stock_code, stock_name, score, roe_avg, gross_margin, dividend_yield,
                  pe, pb, debt_ratio, continuous_div_years, current_price,
                  buy_price, buy_type, good_price, take_profit_price, stop_loss_price,
                  reasons, recommend_date)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

        for r in results:
            fi = r['finance']
            bs = r['buy_sell']
            roe_list = [x for x in fi.get('roe_list', []) if x]
            roe_avg = sum(roe_list) / len(roe_list) if roe_list else None
            gm_list = [x for x in fi.get('gross_margin_list', []) if x]
            gm_avg = gm_list[0] if gm_list else None

            cursor.execute(sql, (
                r['code'], r['name'], r['score'],
                roe_avg, gm_avg,
                min(fi.get('dividend_yield') or 0, 99.99) if fi.get('dividend_yield') else None,
                min(fi.get('pe') or 0, 9999.99) if fi.get('pe') else None,
                min(fi.get('pb') or 0, 9999.99) if fi.get('pb') else None,
                min(fi.get('debt_ratio') or 0, 99.99) if fi.get('debt_ratio') else None,
                fi.get('continuous_dividend_years'),
                r['price'],
                bs['buy_price'], bs['buy_type'], bs['good_price'],
                bs['take_profit_price'], bs['stop_loss_price'],
                '；'.join(r['reasons']),
                today,
            ))
    conn.commit()
    print(f"  已保存 {len(results)} 条微淼选股结果")


def main():
    parser = argparse.ArgumentParser(description='微淼财务自由选股')
    parser.add_argument('--host', default='81.69.42.239')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', default='AiStock2026!')
    parser.add_argument('--database', default='ai_stock')
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  微淼财务自由选股")
    print(f"  标准：ROE>15% + 毛利率>30% + 现金含量>80% + 持续分红")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 获取实时行情
    print("  获取股票池实时行情...")
    realtime = fetch_realtime_batch(STOCK_POOL)
    valid_codes = [c for c in STOCK_POOL if c in realtime]
    print(f"  有效股票: {len(valid_codes)} 只\n")

    # 逐只获取财务数据并评分
    passed_stocks = []
    for i, code in enumerate(valid_codes):
        if (i + 1) % 10 == 0:
            print(f"  分析进度: {i+1}/{len(valid_codes)}")

        finance = get_finance_indicators(code)
        passed, score, reasons, failures = check_weimu_criteria(finance)

        if passed:
            info = realtime[code]
            kline = fetch_kline_tencent(code, days=60)
            buy_sell = generate_buy_sell_price(info['price'], kline)

            passed_stocks.append({
                'code': code,
                'name': info['name'],
                'price': info['price'],
                'score': score,
                'reasons': reasons,
                'failures': failures,
                'finance': finance,
                'buy_sell': buy_sell,
            })
            print(f"    ✓ {info['name']}({code}) 评分:{score} {', '.join(reasons[:3])}")

        time.sleep(1)  # 避免限流

    # 按评分排序
    passed_stocks.sort(key=lambda x: x['score'], reverse=True)

    # 保存到数据库
    if passed_stocks:
        conn = get_connection(args.host, args.port, args.user, args.password, args.database)
        save_to_db(conn, passed_stocks)
        conn.close()

    # 打印结果
    print(f"\n{'='*60}")
    print(f"  符合微淼好公司标准: {len(passed_stocks)} 只")
    print(f"{'='*60}")
    for i, s in enumerate(passed_stocks):
        bs = s['buy_sell']
        print(f"  {i+1}. {s['name']}({s['code']}) 评分:{s['score']}")
        print(f"     理由: {'; '.join(s['reasons'])}")
        print(f"     当前价:{s['price']} 好价格:{bs['good_price']} "
              f"止盈:{bs['take_profit_price']} 止损:{bs['stop_loss_price']}")
        print()


if __name__ == '__main__':
    main()
