"""本地预缓存脚本 v5 — 使用 Scrapling + 东方财富/新浪双源

通过 Scrapling 的 Fetcher（TLS 指纹模拟）请求东方财富和新浪财经 JSON 接口，
获取历史 K 线数据并写入 MySQL 缓存。

使用方法：
    pip install "scrapling[fetchers]"
    scrapling install
    python scripts/prefetch_local.py --host 81.69.42.239 --password AiStock2026!

@author honghui
@version 5.0
@date 2026/06/11
"""
import sys
import os
import time
import random
import argparse
import pymysql
from datetime import datetime

# 将 data-service 加入 Python 路径，以便导入 scrapling_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data-service'))
from app.crawler.scrapling_client import fetch_json, _log


# 股票池（与 data-service/app/stock_data/stock_pool.py 保持一致）
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
    """生成全部 A 股代码候选列表

    @return 代码列表
    @author honghui
    @date 2026/06/11 10:00
    """
    all_codes = []
    for prefix in ['600', '601', '603', '605']:
        for i in range(1000):
            all_codes.append(f'{prefix}{i:03d}')
    for i in range(1, 1000):
        all_codes.append(f'000{i:03d}')
    for i in range(1, 1000):
        all_codes.append(f'002{i:03d}')
    for i in range(1, 2000):
        all_codes.append(f'30{i:04d}')
    return all_codes


def get_stock_pool(pool_type='hs300'):
    """获取股票池

    @param pool_type 池类型: hs300/all/custom
    @return 代码列表
    @author honghui
    @date 2026/06/11 10:00
    """
    if pool_type == 'all':
        print("警告：全部A股约 5000 只，预缓存需要数小时")
        return get_all_a_stocks()
    return STOCK_POOL


def code_to_eastmoney_secid(code):
    """转为东方财富 secid 格式：1.600519（沪）/ 0.000001（深）

    @param code 股票代码
    @return secid 字符串
    @author honghui
    @date 2026/06/11 10:00
    """
    if code.startswith('6'):
        return f'1.{code}'
    else:
        return f'0.{code}'


def code_to_sina_symbol(code):
    """转为新浪格式：sh600519 / sz000001

    @param code 股票代码
    @return 新浪格式代码
    @author honghui
    @date 2026/06/11 10:00
    """
    if code.startswith('6'):
        return f'sh{code}'
    else:
        return f'sz{code}'


def fetch_kline_eastmoney(stock_code, start_date, end_date):
    """从东方财富获取日 K 线数据

    @param stock_code 股票代码
    @param start_date 开始日期 YYYY-MM-DD
    @param end_date 结束日期 YYYY-MM-DD
    @return K 线数据列表，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    secid = code_to_eastmoney_secid(stock_code)
    beg = start_date.replace('-', '')
    end = end_date.replace('-', '')

    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=1&beg={beg}&end={end}"
    )

    data = fetch_json(url, timeout=15)
    if not data:
        return None

    klines_raw = data.get('data', {})
    if not klines_raw:
        return None
    klines = klines_raw.get('klines', [])
    if not klines:
        return None

    result = []
    for line in klines:
        parts = line.split(',')
        if len(parts) < 6:
            continue
        try:
            result.append({
                'date': parts[0],
                'open': float(parts[1]),
                'close': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'volume': int(float(parts[5])),
            })
        except (ValueError, IndexError):
            continue

    return result if result else None


def fetch_kline_sina(stock_code, start_date, end_date):
    """从新浪财经获取日 K 线数据（备用源）

    @param stock_code 股票代码
    @param start_date 开始日期 YYYY-MM-DD
    @param end_date 结束日期 YYYY-MM-DD
    @return K 线数据列表，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    symbol = code_to_sina_symbol(stock_code)
    url = (
        f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
        f"/CN_MarketData.getKLineData"
        f"?symbol={symbol}&scale=240&ma=no&datalen=1500"
    )

    data = fetch_json(url, timeout=15)
    if not data or not isinstance(data, list):
        return None

    result = []
    for item in data:
        try:
            trade_date = item.get('day', '')[:10]
            if trade_date < start_date or trade_date > end_date:
                continue
            result.append({
                'date': trade_date,
                'open': float(item.get('open', 0)),
                'close': float(item.get('close', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'volume': int(float(item.get('volume', 0))),
            })
        except (ValueError, TypeError):
            continue

    return result if result else None


def fetch_kline(stock_code, start_date, end_date):
    """获取日 K 线数据（双源兜底）

    @param stock_code 股票代码
    @param start_date 开始日期
    @param end_date 结束日期
    @return K 线数据列表，全部失败返回空列表
    @author honghui
    @date 2026/06/11 10:00
    """
    data = fetch_kline_eastmoney(stock_code, start_date, end_date)
    if data:
        return data

    _log(f"{stock_code}: 东方财富失败，切换新浪...", '')

    data = fetch_kline_sina(stock_code, start_date, end_date)
    if data:
        return data

    _log(f"{stock_code}: 双源均失败", '')
    return []


def get_connection(host, port, user, password, database):
    """获取 MySQL 连接

    @param host 主机
    @param port 端口
    @param user 用户名
    @param password 密码
    @param database 数据库名
    @return pymysql 连接对象
    @author honghui
    @date 2026/06/11 10:00
    """
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        charset='utf8mb4'
    )


def ensure_table(conn):
    """确保缓存表存在

    @param conn 数据库连接
    @author honghui
    @date 2026/06/11 10:00
    """
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


def save_to_db(conn, stock_code, data_list):
    """写入数据库

    @param conn 数据库连接
    @param stock_code 股票代码
    @param data_list K 线数据列表
    @return 成功写入条数
    @author honghui
    @date 2026/06/11 10:00
    """
    count = 0
    with conn.cursor() as cursor:
        sql = """INSERT IGNORE INTO stock_kline_cache
                 (stock_code, trade_date, open_price, close_price,
                  high_price, low_price, volume, amount)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        for row in data_list:
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


def test_data_source():
    """测试数据源是否可达

    @return 是否至少有一个源可用
    @author honghui
    @date 2026/06/11 10:00
    """
    print("测试数据源连通性...")

    data = fetch_kline_eastmoney('600519', '2026-06-01', '2026-06-10')
    if data:
        print(f"  ✓ 东方财富接口连接成功（茅台 {len(data)} 条数据）\n")
        return True

    data = fetch_kline_sina('600519', '2026-06-01', '2026-06-10')
    if data:
        print(f"  ✓ 新浪财经接口连接成功（茅台 {len(data)} 条数据）\n")
        return True

    print("  ✗ 所有数据源均不可达\n")
    return False


def main():
    """主入口

    @author honghui
    @date 2026/06/11 10:00
    """
    parser = argparse.ArgumentParser(description='使用 Scrapling + 东方财富/新浪 预缓存K线数据')
    parser.add_argument('--host', default='81.69.42.239', help='MySQL主机地址')
    parser.add_argument('--port', type=int, default=3306, help='MySQL端口')
    parser.add_argument('--user', default='root', help='MySQL用户名')
    parser.add_argument('--password', default='root123', help='MySQL密码')
    parser.add_argument('--database', default='ai_stock', help='数据库名')
    parser.add_argument('--start', default='2020-01-01', help='开始日期')
    parser.add_argument('--end', default='2026-06-01', help='结束日期')
    parser.add_argument('--pool', default='hs300',
                        choices=['hs300', 'all', 'custom'],
                        help='股票池: hs300(默认105只) / all(全A股约5000只) / custom(自定义)')
    parser.add_argument('--count', type=int, default=0, help='限制缓存数量（0=不限）')
    args = parser.parse_args()

    # 测试数据源
    if not test_data_source():
        print("数据源不可达，请检查网络")
        return

    # 连接数据库
    print(f"连接 MySQL: {args.host}:{args.port}/{args.database}")
    try:
        conn = get_connection(args.host, args.port, args.user, args.password, args.database)
    except Exception as e:
        print(f"MySQL 连接失败: {e}")
        return

    ensure_table(conn)

    # 获取股票池
    pool = get_stock_pool(args.pool)
    if args.count > 0:
        pool = pool[:args.count]
    total = len(pool)
    success = 0
    fail = 0

    print(f"开始预缓存 {total} 只股票 ({args.start} ~ {args.end})...\n")

    # 断点续传：查询已缓存的股票
    cached_stocks = set()
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT stock_code FROM stock_kline_cache WHERE trade_date >= %s", (args.start,))
        for row in cursor.fetchall():
            cached_stocks.add(row[0] if isinstance(row, tuple) else row.get('stock_code', ''))
    if cached_stocks:
        print(f"  已缓存 {len(cached_stocks)} 只，将跳过\n")

    for i, code in enumerate(pool):
        if code in cached_stocks:
            print(f"  [{i+1}/{total}] {code}: 已缓存，跳过")
            success += 1
            continue

        data = fetch_kline(code, args.start, args.end)
        if data:
            rows = save_to_db(conn, code, data)
            if rows > 0:
                success += 1
                print(f"  [{i+1}/{total}] {code}: {rows} 条K线 ✓")
            else:
                fail += 1
                print(f"  [{i+1}/{total}] {code}: 日期范围内无有效数据 ✗")
        else:
            fail += 1
            print(f"  [{i+1}/{total}] {code}: 获取失败 ✗")

        time.sleep(random.uniform(3, 5))

    conn.close()

    print(f"\n{'='*50}")
    print(f"完成! 成功: {success}, 失败: {fail}, 总计: {total}")
    if total > 0:
        print(f"成功率: {success/total*100:.1f}%")


if __name__ == '__main__':
    main()
