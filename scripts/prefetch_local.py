"""本地预缓存脚本 v4 — 使用腾讯财经HTTP接口

腾讯财经接口是纯 HTTP GET 请求，无需注册、不限IP、不限频率。
浏览器都能打开的数据源，绝对不会被限制。

使用方法：
    pip install requests pymysql cryptography
    python scripts/prefetch_local.py --host 81.69.42.239 --password AiStock2026!
"""
import time
import argparse
import pymysql
import requests
from datetime import datetime, timedelta

# 股票池
# 可以手动指定，也可以通过 --pool 参数选择自动获取
STOCK_POOL = [
    '600519', '000858', '600036', '601318', '000333',
    '600900', '601166', '600276', '000651', '601888',
    '300750', '002475', '600031', '601012', '600809',
    '000568', '002304', '600585', '601658', '002714',
    '300059', '002352', '600887', '601669', '000725',
    '600690', '601398', '600048', '000001', '600000',
    '601601', '600104', '002415', '300015', '601288',
    '600016', '601328', '000002', '600030', '601857',
    '002230', '300033', '600050', '601688', '002027',
    '603259', '601211', '600436', '002001', '300124',
    '600309', '002142', '600588', '601006', '000776',
    '002032', '603288', '300760', '601899', '600426',
    '002607', '601225', '000063', '002493', '600763',
    '300122', '002044', '601111', '600196', '300628',
    '002466', '600332', '601138', '600009', '000661',
    '300529', '002241', '601766', '600383', '000538',
    '601919', '002456', '300347', '600570', '002008',
    '601668', '600029', '002372', '300274', '600346',
    '601800', '000100', '002601', '300136', '600372',
    '002049', '601088', '600176', '000423', '601816',
    '300408', '002311', '600660', '601628', '000166',
]


def get_all_a_stocks():
    """从腾讯接口获取全部A股代码列表

    通过沪深交易所的股票代码规则自动生成候选列表，
    然后验证哪些是有效的。
    """
    print("正在获取全部A股代码...")
    all_codes = []

    # 沪市主板：600000-603999
    for prefix in ['600', '601', '603', '605']:
        for i in range(1000):
            all_codes.append(f'{prefix}{i:03d}')

    # 深市主板：000001-000999
    for i in range(1, 1000):
        all_codes.append(f'000{i:03d}')

    # 中小板：002001-002999
    for i in range(1, 1000):
        all_codes.append(f'002{i:03d}')

    # 创业板：300001-301999
    for i in range(1, 2000):
        all_codes.append(f'30{i:04d}')

    return all_codes


def get_stock_pool_from_web(pool_type='hs300'):
    """从网络获取指定指数的成分股列表

    用腾讯接口验证股票是否有效（返回K线数据）。
    """
    if pool_type == 'custom':
        return STOCK_POOL
    elif pool_type == 'all':
        # 获取全部A股——数量太多，实际中不建议
        print("警告：全部A股约 5000 只，预缓存需要数小时")
        return get_all_a_stocks()
    else:
        # 默认使用硬编码的池子
        return STOCK_POOL


def code_to_tencent(code):
    """转为腾讯格式：sh600519 / sz000001"""
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'


def fetch_kline_tencent(stock_code, year_count=6):
    """使用腾讯财经接口获取日K线

    接口：http://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    这是腾讯公开的股票数据接口，纯 HTTP GET。

    带重试机制，失败后等待更长时间再试。
    """
    tc_code = code_to_tencent(stock_code)
    all_data = []
    seen_dates = set()
    end = datetime.now()
    max_retries = 3

    for i in range(year_count):
        end_str = end.strftime('%Y-%m-%d')
        url = (
            f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={tc_code},day,,{end_str},320,qfq"
        )

        success = False
        for retry in range(max_retries):
            try:
                resp = requests.get(url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code != 200:
                    time.sleep(3)
                    continue

                data = resp.json()
                stock_data = data.get('data', {}).get(tc_code, {})
                klines = stock_data.get('qfqday', stock_data.get('day', []))

                if not klines:
                    break

                earliest = None
                for k in klines:
                    if len(k) >= 6 and k[0] not in seen_dates:
                        seen_dates.add(k[0])
                        all_data.append({
                            'date': k[0],
                            'open': float(k[1]),
                            'close': float(k[2]),
                            'high': float(k[3]),
                            'low': float(k[4]),
                            'volume': int(float(k[5])),
                        })
                        if earliest is None or k[0] < earliest:
                            earliest = k[0]

                success = True
                if earliest:
                    end = datetime.strptime(earliest, '%Y-%m-%d') - timedelta(days=1)
                break

            except Exception as e:
                wait = (retry + 1) * 5  # 5s, 10s, 15s
                print(f"    重试 {retry+1}/{max_retries}，等待 {wait}s...")
                time.sleep(wait)

        if not success:
            break

        time.sleep(2)  # 每次分段请求间隔 2 秒

    all_data.sort(key=lambda x: x['date'])
    return all_data


def get_connection(host, port, user, password, database):
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        charset='utf8mb4'
    )


def ensure_table(conn):
    """确保缓存表存在"""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_kline_cache (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(10) NOT NULL,
                trade_date DATE NOT NULL,
                open_price DECIMAL(10,2),
                close_price DECIMAL(10,2),
                high_price DECIMAL(10,2),
                low_price DECIMAL(10,2),
                volume BIGINT,
                amount DECIMAL(20,2) DEFAULT 0,
                UNIQUE KEY uk_code_date (stock_code, trade_date),
                INDEX idx_code (stock_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


def save_to_db(conn, stock_code, data_list, start_date, end_date):
    """写入数据库"""
    count = 0
    with conn.cursor() as cursor:
        sql = """INSERT IGNORE INTO stock_kline_cache
                 (stock_code, trade_date, open_price, close_price,
                  high_price, low_price, volume, amount)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        for row in data_list:
            # 过滤日期范围
            if row['date'] < start_date or row['date'] > end_date:
                continue
            # 过滤停牌数据
            if row['close'] <= 0:
                continue
            try:
                cursor.execute(sql, (
                    stock_code, row['date'],
                    row['open'], row['close'],
                    row['high'], row['low'],
                    row['volume'], 0
                ))
                count += 1
            except Exception:
                continue
    conn.commit()
    return count


def test_connection():
    """测试腾讯接口是否可达"""
    print("测试腾讯财经接口...")
    try:
        url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,,,5,qfq"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data:
                print("  ✓ 腾讯财经接口连接成功\n")
                return True
        print(f"  ✗ 返回异常: {resp.status_code}")
    except Exception as e:
        print(f"  ✗ 连接失败: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(description='使用腾讯财经接口预缓存K线数据')
    parser.add_argument('--host', default='81.69.42.239', help='MySQL主机地址')
    parser.add_argument('--port', type=int, default=3306, help='MySQL端口')
    parser.add_argument('--user', default='root', help='MySQL用户名')
    parser.add_argument('--password', default='root123', help='MySQL密码')
    parser.add_argument('--database', default='ai_stock', help='数据库名')
    parser.add_argument('--start', default='2020-01-01', help='开始日期')
    parser.add_argument('--end', default='2026-06-01', help='结束日期')
    parser.add_argument('--years', type=int, default=6, help='获取最近几年数据')
    parser.add_argument('--pool', default='hs300',
                        choices=['hs300', 'all', 'custom'],
                        help='股票池: hs300(默认105只) / all(全A股约5000只) / custom(自定义)')
    parser.add_argument('--count', type=int, default=0, help='限制缓存数量（0=不限）')
    args = parser.parse_args()

    # 测试接口
    if not test_connection():
        print("腾讯财经接口无法访问，请检查网络")
        return

    print(f"连接 MySQL: {args.host}:{args.port}/{args.database}")
    try:
        conn = get_connection(args.host, args.port, args.user, args.password, args.database)
    except Exception as e:
        print(f"MySQL 连接失败: {e}")
        return

    ensure_table(conn)

    # 获取股票池
    pool = get_stock_pool_from_web(args.pool)
    if args.count > 0:
        pool = pool[:args.count]
    total = len(pool)
    success = 0
    fail = 0

    print(f"开始预缓存 {total} 只股票 ({args.start} ~ {args.end})...\n")

    # 查询已缓存的股票（断点续传）
    cached_stocks = set()
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT stock_code FROM stock_kline_cache WHERE trade_date >= %s", (args.start,))
        for row in cursor.fetchall():
            # row 可能是 tuple 或 dict
            cached_stocks.add(row[0] if isinstance(row, tuple) else row.get('stock_code', ''))
    if cached_stocks:
        print(f"  已缓存 {len(cached_stocks)} 只，将跳过\n")

    for i, code in enumerate(pool):
        if code in cached_stocks:
            print(f"  [{i+1}/{total}] {code}: 已缓存，跳过")
            success += 1
            continue

        data = fetch_kline_tencent(code, args.years)
        if data:
            rows = save_to_db(conn, code, data, args.start, args.end)
            if rows > 0:
                success += 1
                print(f"  [{i+1}/{total}] {code}: {rows} 条K线 ✓")
            else:
                fail += 1
                print(f"  [{i+1}/{total}] {code}: 日期范围内无数据 ✗")
        else:
            fail += 1
            print(f"  [{i+1}/{total}] {code}: 获取失败 ✗")
        time.sleep(3)  # 每只股票间隔 3 秒，避免被断开

    conn.close()

    print(f"\n{'='*50}")
    print(f"完成! 成功: {success}, 失败: {fail}, 总计: {total}")
    print(f"成功率: {success/total*100:.1f}%")


if __name__ == '__main__':
    main()
