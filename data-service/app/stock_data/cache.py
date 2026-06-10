"""K线数据缓存模块

回测引擎优先从 MySQL 缓存读取历史K线数据。
如果缓存缺失，尝试从 AkShare 补充。
解决 Docker 容器内 AkShare 网络不稳定的问题。

使用方式：
1. 在网络好的环境调用 prefetch_all() 一次性灌入历史数据
2. 之后回测直接调 get_kline_cached() 从缓存读取
"""
import time
import pandas as pd
from app.db import get_connection
from app.stock_data.stock_pool import STOCK_POOL


def get_kline_cached(stock_code, start_date, end_date):
    """获取K线数据（只读缓存，不调外部接口）

    回测时只从 MySQL 缓存读取，避免被 AkShare 限流。
    缓存没有数据就返回空，跳过该股票。

    Args:
        stock_code: 股票代码
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'

    Returns:
        DataFrame 包含列: 日期/开盘/收盘/最高/最低/成交量
        如果无数据返回空 DataFrame
    """
    cached = _read_from_db(stock_code, start_date, end_date)
    if cached is not None and len(cached) >= 5:
        return cached
    return pd.DataFrame()


def prefetch_all(start_date='2020-01-01', end_date='2026-06-01'):
    """批量预缓存所有股票池的K线数据

    在网络通畅的环境执行一次即可。
    之后 Docker 内的回测直接读缓存。

    Returns:
        dict: {'success': int, 'fail': int, 'total': int}
    """
    success = 0
    fail = 0
    total = len(STOCK_POOL)

    print(f"开始预缓存 {total} 只股票的K线数据 ({start_date} ~ {end_date})...")

    for i, code in enumerate(STOCK_POOL):
        try:
            fresh = _fetch_from_akshare(code, start_date, end_date)
            if fresh is not None and not fresh.empty:
                _save_to_db(code, fresh)
                success += 1
                if (i + 1) % 10 == 0:
                    print(f"  进度: {i+1}/{total}，成功: {success}")
            else:
                fail += 1
                print(f"  {code}: 无数据")
        except Exception as e:
            fail += 1
            print(f"  {code}: 失败 - {e}")
        time.sleep(1.0)  # 每只股票间隔 1 秒，避免限流

    print(f"预缓存完成: 成功 {success}, 失败 {fail}, 总计 {total}")
    return {'success': success, 'fail': fail, 'total': total}


def get_cache_stats():
    """获取缓存统计信息"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 先确认表存在
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

            cursor.execute("SELECT COUNT(DISTINCT stock_code) as stocks, COUNT(*) as rows_count FROM stock_kline_cache")
            stats = cursor.fetchone()
            cursor.execute("SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date FROM stock_kline_cache")
            dates = cursor.fetchone()
            return {
                'cached_stocks': stats.get('stocks', 0) if stats else 0,
                'total_rows': stats.get('rows_count', 0) if stats else 0,
                'date_range': {
                    'from': str(dates.get('min_date', '')) if dates and dates.get('min_date') else None,
                    'to': str(dates.get('max_date', '')) if dates and dates.get('max_date') else None,
                }
            }
    except Exception as e:
        return {'error': str(e), 'cached_stocks': 0, 'total_rows': 0}
    finally:
        conn.close()


def _read_from_db(stock_code, start_date, end_date):
    """从 MySQL 缓存读取K线"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT trade_date, open_price, close_price, high_price,
                            low_price, volume, amount
                     FROM stock_kline_cache
                     WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
                     ORDER BY trade_date"""
            cursor.execute(sql, (stock_code, start_date, end_date))
            rows = cursor.fetchall()
            if not rows:
                return None
            df = pd.DataFrame(rows)
            df.columns = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
            # 确保数值类型
            for col in ['开盘', '收盘', '最高', '最低', '成交额']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['成交量'] = pd.to_numeric(df['成交量'], errors='coerce').fillna(0).astype(int)
            return df
    except Exception as e:
        print(f"  缓存读取失败 {stock_code}: {e}")
        return None
    finally:
        conn.close()


def _fetch_from_akshare(stock_code, start_date, end_date):
    """从 AkShare 获取K线数据"""
    try:
        import akshare as ak
        start_fmt = start_date.replace('-', '')
        end_fmt = end_date.replace('-', '')
        df = ak.stock_zh_a_hist(
            symbol=stock_code, period="daily",
            start_date=start_fmt, end_date=end_fmt, adjust="qfq"
        )
        if df is not None and not df.empty:
            # 统一列名（AkShare 返回的列名可能是中文）
            col_map = {
                '日期': '日期', '开盘': '开盘', '收盘': '收盘',
                '最高': '最高', '最低': '最低', '成交量': '成交量', '成交额': '成交额'
            }
            df = df.rename(columns=col_map)
            needed_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
            existing_cols = [c for c in needed_cols if c in df.columns]
            return df[existing_cols]
    except Exception as e:
        print(f"  AkShare 获取 {stock_code} 失败: {e}")
    return None


def _save_to_db(stock_code, df):
    """将K线数据写入缓存"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT IGNORE INTO stock_kline_cache
                     (stock_code, trade_date, open_price, close_price, high_price,
                      low_price, volume, amount)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            for _, row in df.iterrows():
                try:
                    amount = float(row.get('成交额', 0)) if '成交额' in row.index else 0
                    cursor.execute(sql, (
                        stock_code, str(row['日期']),
                        float(row['开盘']), float(row['收盘']),
                        float(row['最高']), float(row['最低']),
                        int(row['成交量']), amount
                    ))
                except (ValueError, KeyError):
                    continue
        conn.commit()
    except Exception as e:
        print(f"  缓存写入失败 {stock_code}: {e}")
    finally:
        conn.close()
