# Scrapling 爬虫改造实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 K 线数据获取和政策资讯爬虫从失效的腾讯财经接口 + requests 迁移到 Scrapling 框架（Fetcher → StealthyFetcher 降级），并扩展国际财经数据源。

**架构：** 新增 `scrapling_client.py` 统一封装降级请求逻辑。K 线获取改用东方财富+新浪双源。政策爬虫扩展 8 个数据源（3 国内 + 5 国际）。命令行接口保持不变。

**技术栈：** Python 3.10+, Scrapling (fetchers), pymysql, BeautifulSoup4

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `data-service/app/crawler/scrapling_client.py` | **新增** — 封装 Fetcher→StealthyFetcher 降级逻辑，提供 `fetch_url()` 和 `fetch_json()` |
| `data-service/app/crawler/policy_crawler.py` | **重写** — 替换 requests，新增国际数据源解析器 |
| `scripts/prefetch_local.py` | **重写** — 东方财富+新浪双源获取 K 线，底层调用 scrapling_client |
| `data-service/app/stock_data/cache.py` | **修改** — `_fetch_from_akshare` 替换为东方财富接口 |
| `data-service/requirements.txt` | **修改** — 新增 scrapling 依赖 |

---

## 任务 1：更新依赖配置

**文件：**
- 修改：`data-service/requirements.txt`

- [ ] **步骤 1：更新 requirements.txt**

在 `data-service/requirements.txt` 末尾追加 scrapling 依赖，移除不再直接使用的 requests（但保留，因为其他模块可能用到）：

```txt
fastapi==0.104.1
uvicorn==0.24.0
akshare>=1.18.60
beautifulsoup4==4.12.2
requests==2.31.0
pymysql==1.1.0
cryptography==41.0.7
sqlalchemy==2.0.23
redis==5.0.1
apscheduler==3.10.4
scrapling[fetchers]>=0.2.9
```

- [ ] **步骤 2：安装依赖并验证**

运行：
```bash
pip install "scrapling[fetchers]"
scrapling install
```

验证：
```bash
python -c "from scrapling.fetchers import Fetcher, StealthyFetcher; print('OK')"
```
预期输出：`OK`

- [ ] **步骤 3：Commit**

```bash
git add data-service/requirements.txt
git commit -m "build: 添加 scrapling[fetchers] 依赖"
```

---

## 任务 2：实现 scrapling_client.py 降级封装模块

**文件：**
- 创建：`data-service/app/crawler/scrapling_client.py`

- [ ] **步骤 1：创建 scrapling_client.py**

```python
"""Scrapling 请求客户端封装模块

统一封装 Fetcher → StealthyFetcher 降级逻辑。
所有爬虫模块通过此模块发起 HTTP 请求，替代原来的 requests 库。

@author honghui
@version 1.0
@date 2026/06/11
"""
import json
from datetime import datetime
from scrapling.fetchers import Fetcher, StealthyFetcher


def fetch_url(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回 HTML 字符串

    降级策略：
    1. Fetcher(impersonate='chrome') + stealthy_headers
    2. Fetcher(impersonate='firefox') + stealthy_headers
    3. StealthyFetcher(headless=True)

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return HTML 字符串，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：Fetcher + Chrome 指纹
    result = _try_fetcher(url, impersonate='chrome', timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + Firefox 指纹
    result = _try_fetcher(url, impersonate='firefox', timeout=timeout)
    if result is not None:
        return result

    # 第 3 层：StealthyFetcher（真实浏览器）
    result = _try_stealthy(url, timeout=30)
    if result is not None:
        return result

    return None


def fetch_json(url, timeout=15, max_retries=2):
    """获取 URL 内容，返回解析后的 JSON dict

    降级策略与 fetch_url 相同，额外做 JSON 解析。

    @param url 目标 URL
    @param timeout 超时时间（秒）
    @param max_retries 每层重试次数
    @return dict，失败返回 None
    @author honghui
    @date 2026/06/11 10:00
    """
    # 第 1 层：Fetcher + Chrome 指纹
    result = _try_fetcher_json(url, impersonate='chrome', timeout=timeout)
    if result is not None:
        return result

    # 第 2 层：Fetcher + Firefox 指纹
    result = _try_fetcher_json(url, impersonate='firefox', timeout=timeout)
    if result is not None:
        return result

    # 第 3 层：StealthyFetcher（真实浏览器）— 获取页面文本后尝试 JSON 解析
    text = _try_stealthy(url, timeout=30)
    if text is not None:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _try_fetcher(url, impersonate='chrome', timeout=15):
    """尝试使用 Fetcher 获取 URL，返回文本或 None

    @param url 目标 URL
    @param impersonate 模拟的浏览器指纹
    @param timeout 超时时间
    @return 页面文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200:
            return page.text
        _log(f"Fetcher({impersonate}) 状态码异常: {page.status if page else 'None'}", url)
    except Exception as e:
        _log(f"Fetcher({impersonate}) 失败: {e}", url)
    return None


def _try_fetcher_json(url, impersonate='chrome', timeout=15):
    """尝试使用 Fetcher 获取 JSON，返回 dict 或 None

    @param url 目标 URL
    @param impersonate 模拟的浏览器指纹
    @param timeout 超时时间
    @return dict 或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=timeout)
        if page and page.status == 200:
            text = page.text
            if text:
                return json.loads(text)
        _log(f"Fetcher({impersonate}) JSON 状态码: {page.status if page else 'None'}", url)
    except json.JSONDecodeError as e:
        _log(f"Fetcher({impersonate}) JSON 解析失败: {e}", url)
    except Exception as e:
        _log(f"Fetcher({impersonate}) JSON 请求失败: {e}", url)
    return None


def _try_stealthy(url, timeout=30):
    """使用 StealthyFetcher 获取页面内容

    @param url 目标 URL
    @param timeout 超时时间
    @return 页面 HTML 文本或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        _log("降级使用 StealthyFetcher...", url)
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        if page:
            return page.html_content
    except Exception as e:
        _log(f"StealthyFetcher 失败: {e}", url)
    return None


def _log(message, url=''):
    """输出日志

    @param message 日志内容
    @param url 相关 URL
    @author honghui
    @date 2026/06/11 10:00
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    url_short = url[:60] + '...' if len(url) > 60 else url
    print(f"[{timestamp}] [scrapling_client] {message} | {url_short}")
```

- [ ] **步骤 2：验证模块可导入**

运行：
```bash
python -c "import sys; sys.path.insert(0, 'data-service'); from app.crawler.scrapling_client import fetch_url, fetch_json; print('import OK')"
```
预期输出：`import OK`

- [ ] **步骤 3：Commit**

```bash
git add data-service/app/crawler/scrapling_client.py
git commit -m "feat: 新增 scrapling_client 降级请求封装模块"
```

---

## 任务 3：重写 prefetch_local.py（东方财富+新浪双源）

**文件：**
- 重写：`scripts/prefetch_local.py`

- [ ] **步骤 1：重写 prefetch_local.py**

```python
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
        # 格式: "2024-01-02,1688.00,1695.50,1700.00,1680.00,25000,4200000000.00,1.5,..."
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

    新浪接口一次最多返回约 1000 条数据，足够覆盖 4-5 年日线。

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
            trade_date = item.get('day', '')[:10]  # 截取日期部分
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

    优先东方财富，失败切新浪。

    @param stock_code 股票代码
    @param start_date 开始日期
    @param end_date 结束日期
    @return K 线数据列表，全部失败返回空列表
    @author honghui
    @date 2026/06/11 10:00
    """
    # 优先东方财富
    data = fetch_kline_eastmoney(stock_code, start_date, end_date)
    if data:
        return data

    _log(f"{stock_code}: 东方财富失败，切换新浪...", '')

    # 备用新浪
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

    # 测试东方财富
    data = fetch_kline_eastmoney('600519', '2026-06-01', '2026-06-10')
    if data:
        print(f"  ✓ 东方财富接口连接成功（茅台 {len(data)} 条数据）\n")
        return True

    # 测试新浪
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

        time.sleep(3)

    conn.close()

    print(f"\n{'='*50}")
    print(f"完成! 成功: {success}, 失败: {fail}, 总计: {total}")
    if total > 0:
        print(f"成功率: {success/total*100:.1f}%")


if __name__ == '__main__':
    main()
```

- [ ] **步骤 2：验证脚本参数兼容性**

运行（不实际执行，只验证参数解析）：
```bash
python scripts/prefetch_local.py --help
```
预期输出包含 `--host`、`--port`、`--user`、`--password`、`--database`、`--start`、`--end`、`--pool`、`--count` 参数说明。

- [ ] **步骤 3：Commit**

```bash
git add scripts/prefetch_local.py
git commit -m "feat: 重写预缓存脚本，使用 Scrapling + 东方财富/新浪双源"
```

---

## 任务 4：重写 policy_crawler.py（扩展国际数据源）

**文件：**
- 重写：`data-service/app/crawler/policy_crawler.py`

- [ ] **步骤 1：重写 policy_crawler.py**

```python
"""政策资讯爬虫模块

使用 Scrapling 爬取国内外政策及财经资讯网站，提取最新资讯入库。
数据源覆盖国务院、证监会、央行、Reuters、CNBC、SCMP、Investing.com、美联储。

@author honghui
@version 2.0
@date 2026/06/11
"""
from bs4 import BeautifulSoup
from datetime import datetime
from app.db import get_connection
from app.crawler.scrapling_client import fetch_url


# 数据源配置
SOURCES = {
    # === 国内政策 ===
    '国务院': {
        'url': 'https://www.gov.cn/zhengce/zuixin/index.htm',
        'parser': 'parse_gov_cn',
        'category': 'domestic',
        'language': 'zh',
    },
    '证监会': {
        'url': 'http://www.csrc.gov.cn/csrc/c100028/common_list.shtml',
        'parser': 'parse_csrc',
        'category': 'domestic',
        'language': 'zh',
    },
    '央行': {
        'url': 'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html',
        'parser': 'parse_pbc',
        'category': 'domestic',
        'language': 'zh',
    },
    # === 国际财经 ===
    'Reuters': {
        'url': 'https://www.reuters.com/business/',
        'parser': 'parse_reuters',
        'category': 'international',
        'language': 'en',
    },
    'CNBC': {
        'url': 'https://www.cnbc.com/world/',
        'parser': 'parse_cnbc',
        'category': 'international',
        'language': 'en',
    },
    'SCMP': {
        'url': 'https://www.scmp.com/business',
        'parser': 'parse_scmp',
        'category': 'international',
        'language': 'en',
    },
    'Investing': {
        'url': 'https://www.investing.com/news/stock-market-news',
        'parser': 'parse_investing',
        'category': 'international',
        'language': 'en',
    },
    # === 美联储 ===
    'FederalReserve': {
        'url': 'https://www.federalreserve.gov/newsevents/pressreleases.htm',
        'parser': 'parse_fed',
        'category': 'fed',
        'language': 'en',
    },
}


# ========== 国内解析器 ==========

def parse_gov_cn(html, base_url='https://www.gov.cn'):
    """解析国务院最新政策页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('a[href*="/zhengce/"]')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


def parse_csrc(html, base_url='http://www.csrc.gov.cn'):
    """解析证监会页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.list_content a, .commonlist a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


def parse_pbc(html, base_url='http://www.pbc.gov.cn'):
    """解析央行页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for link in soup.select('.newslist_style a, .cate_content a')[:20]:
        title = link.get_text(strip=True)
        href = link.get('href', '')
        if not title or len(title) < 5:
            continue
        if not href.startswith('http'):
            href = base_url + href
        items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
    return items


# ========== 国际解析器 ==========

def parse_reuters(html, base_url='https://www.reuters.com'):
    """解析 Reuters Business 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    # Reuters 文章链接通常在 a[data-testid] 或 a[href*="/business/"]
    selectors = [
        'a[data-testid*="Heading"]',
        'a[href*="/business/"]',
        'a[href*="/markets/"]',
        'h3 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_cnbc(html, base_url='https://www.cnbc.com'):
    """解析 CNBC World 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        '.Card-title a',
        'a[href*="/world/"]',
        'a[href*="/economy/"]',
        '.RiverHeadline a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_scmp(html, base_url='https://www.scmp.com'):
    """解析 South China Morning Post Business 页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        'a[href*="/business/"]',
        'a[href*="/economy/"]',
        '.article-title a',
        'h2 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_investing(html, base_url='https://www.investing.com'):
    """解析 Investing.com 股市新闻页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        'a[href*="/news/stock-market-news/"]',
        '.articleItem a',
        'article a[href*="/news/"]',
        '.textDiv a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


def parse_fed(html, base_url='https://www.federalreserve.gov'):
    """解析美联储新闻发布页面

    @param html HTML 文本
    @param base_url 基础 URL
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    selectors = [
        '.newsitem a',
        'a[href*="/newsevents/pressreleases/"]',
        '.row .col-xs-9 a',
    ]
    seen_urls = set()
    for selector in selectors:
        for link in soup.select(selector)[:15]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if not title or len(title) < 10:
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({'title': title, 'url': href, 'publish_time': datetime.now()})
        if len(items) >= 15:
            break
    return items[:15]


# ========== 解析器注册 ==========

PARSERS = {
    'parse_gov_cn': parse_gov_cn,
    'parse_csrc': parse_csrc,
    'parse_pbc': parse_pbc,
    'parse_reuters': parse_reuters,
    'parse_cnbc': parse_cnbc,
    'parse_scmp': parse_scmp,
    'parse_investing': parse_investing,
    'parse_fed': parse_fed,
}


# ========== 业务逻辑 ==========

def crawl_source(source_name, source_config):
    """爬取单个数据源

    @param source_name 数据源名称
    @param source_config 数据源配置
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    url = source_config['url']
    parser_name = source_config['parser']
    parser = PARSERS.get(parser_name)
    category = source_config.get('category', 'domestic')
    language = source_config.get('language', 'zh')

    if not parser:
        return []

    try:
        html = fetch_url(url)
        if not html:
            print(f"[{datetime.now()}] 爬取 {source_name} 失败: 无法获取页面内容")
            return []

        items = parser(html)
        # 补充 source/category/language 字段
        for item in items:
            item['source'] = source_name
            item['category'] = category
            item['language'] = language
            if 'publish_time' not in item:
                item['publish_time'] = datetime.now()

        return items
    except Exception as e:
        print(f"[{datetime.now()}] 爬取 {source_name} 失败: {e}")
        return []


def save_news(item):
    """保存资讯到数据库（去重）

    @param item 资讯 dict
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """INSERT IGNORE INTO policy_news
                     (source, title, url, publish_time, category, language)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (
                item['source'],
                item['title'],
                item['url'],
                item['publish_time'],
                item.get('category', 'domestic'),
                item.get('language', 'zh'),
            ))
        conn.commit()
    finally:
        conn.close()


def crawl_all_sources():
    """爬取所有数据源（定时任务调用）

    @author honghui
    @date 2026/06/11 10:00
    """
    total = 0
    for name, config in SOURCES.items():
        items = crawl_source(name, config)
        for item in items:
            save_news(item)
        total += len(items)
        print(f"[{datetime.now()}] {name}: {len(items)} 条")
    print(f"[{datetime.now()}] 爬取完成，共 {total} 条资讯")


def get_latest_news(limit=20):
    """获取最新资讯列表

    @param limit 返回条数
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM policy_news ORDER BY created_at DESC LIMIT %s"
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            for r in results:
                if r.get('publish_time'):
                    r['publish_time'] = r['publish_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()


def search_news(keyword, limit=20):
    """按关键词搜索资讯

    @param keyword 关键词
    @param limit 返回条数
    @return 资讯列表
    @author honghui
    @date 2026/06/11 10:00
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """SELECT * FROM policy_news
                     WHERE title LIKE %s OR keywords LIKE %s
                     ORDER BY created_at DESC LIMIT %s"""
            like_keyword = f'%{keyword}%'
            cursor.execute(sql, (like_keyword, like_keyword, limit))
            results = cursor.fetchall()
            for r in results:
                if r.get('publish_time'):
                    r['publish_time'] = r['publish_time'].strftime('%Y-%m-%d %H:%M:%S')
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            return results
    finally:
        conn.close()
```

- [ ] **步骤 2：验证模块可导入**

运行：
```bash
python -c "import sys; sys.path.insert(0, 'data-service'); from app.crawler.policy_crawler import SOURCES, PARSERS; print(f'数据源: {len(SOURCES)} 个, 解析器: {len(PARSERS)} 个')"
```
预期输出：`数据源: 8 个, 解析器: 8 个`

- [ ] **步骤 3：Commit**

```bash
git add data-service/app/crawler/policy_crawler.py
git commit -m "feat: 重写政策爬虫，使用 Scrapling 并扩展国际数据源"
```

---

## 任务 5：修改 cache.py 替换 AkShare 数据获取

**文件：**
- 修改：`data-service/app/stock_data/cache.py`（仅修改 `_fetch_from_akshare` 函数）

- [ ] **步骤 1：替换 `_fetch_from_akshare` 为东方财富接口**

将 `cache.py` 中的 `_fetch_from_akshare` 函数替换为：

```python
def _fetch_from_akshare(stock_code, start_date, end_date):
    """从东方财富获取K线数据（替代原 AkShare）

    使用 Scrapling 的 Fetcher 发起请求，绕过 TLS 指纹检测。

    @param stock_code 股票代码
    @param start_date 开始日期 YYYY-MM-DD
    @param end_date 结束日期 YYYY-MM-DD
    @return DataFrame 或 None
    @author honghui
    @date 2026/06/11 10:00
    """
    try:
        from app.crawler.scrapling_client import fetch_json

        # 构造东方财富请求
        secid = f'1.{stock_code}' if stock_code.startswith('6') else f'0.{stock_code}'
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

        # 解析为 DataFrame
        rows = []
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 7:
                rows.append({
                    '日期': parts[0],
                    '开盘': float(parts[1]),
                    '收盘': float(parts[2]),
                    '最高': float(parts[3]),
                    '最低': float(parts[4]),
                    '成交量': int(float(parts[5])),
                    '成交额': float(parts[6]) if len(parts) > 6 else 0,
                })

        if rows:
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"  东方财富获取 {stock_code} 失败: {e}")
    return None
```

- [ ] **步骤 2：验证 cache.py 可导入**

运行：
```bash
python -c "import sys; sys.path.insert(0, 'data-service'); from app.stock_data.cache import get_kline_cached, prefetch_all; print('OK')"
```
预期输出：`OK`

- [ ] **步骤 3：Commit**

```bash
git add data-service/app/stock_data/cache.py
git commit -m "refactor: cache.py 替换 AkShare 为东方财富接口"
```

---

## 任务 6：数据库表结构变更

**文件：**
- 无代码文件变更，执行 SQL

- [ ] **步骤 1：执行 ALTER TABLE 添加新字段**

连接 MySQL 执行：
```sql
ALTER TABLE policy_news ADD COLUMN category VARCHAR(20) DEFAULT 'domestic' COMMENT '分类: domestic/international/fed';
ALTER TABLE policy_news ADD COLUMN language VARCHAR(10) DEFAULT 'zh' COMMENT '语言: zh/en';
```

如果字段已存在会报错，可忽略。

- [ ] **步骤 2：验证字段存在**

```sql
DESCRIBE policy_news;
```

确认 `category` 和 `language` 两个字段存在。

- [ ] **步骤 3：Commit（记录 SQL 变更）**

创建 `scripts/sql/2026-06-11-add-news-fields.sql` 文件保存此变更：

```sql
-- 政策资讯表新增分类和语言字段
ALTER TABLE policy_news ADD COLUMN category VARCHAR(20) DEFAULT 'domestic' COMMENT '分类: domestic/international/fed';
ALTER TABLE policy_news ADD COLUMN language VARCHAR(10) DEFAULT 'zh' COMMENT '语言: zh/en';
```

```bash
git add scripts/sql/2026-06-11-add-news-fields.sql
git commit -m "feat: policy_news 表新增 category 和 language 字段"
```

---

## 任务 7：端到端验证

- [ ] **步骤 1：验证 K 线数据获取**

```bash
python scripts/prefetch_local.py --host 81.69.42.239 --password AiStock2026! --pool hs300 --count 3
```

预期：成功获取 3 只股票的 K 线数据并写入数据库，输出类似：
```
测试数据源连通性...
  ✓ 东方财富接口连接成功（茅台 X 条数据）
连接 MySQL: 81.69.42.239:3306/ai_stock
开始预缓存 3 只股票 (2020-01-01 ~ 2026-06-01)...
  [1/3] 600519: XXX 条K线 ✓
  [2/3] 000858: XXX 条K线 ✓
  [3/3] 600036: XXX 条K线 ✓
==================================================
完成! 成功: 3, 失败: 0, 总计: 3
成功率: 100.0%
```

- [ ] **步骤 2：验证政策资讯爬取**

启动 data-service 后调用手动爬取接口：
```bash
curl -X POST http://localhost:8001/api/news/crawl
```

或直接 Python 测试：
```bash
python -c "import sys; sys.path.insert(0, 'data-service'); from app.crawler.policy_crawler import crawl_source, SOURCES; items = crawl_source('Reuters', SOURCES['Reuters']); print(f'Reuters: {len(items)} 条')"
```

预期：至少部分数据源能获取到数据。

- [ ] **步骤 3：验证断点续传**

重新运行步骤 1 的命令，预期已缓存的股票被跳过：
```
  已缓存 3 只，将跳过
  [1/3] 600519: 已缓存，跳过
  ...
```

- [ ] **步骤 4：最终 Commit**

如有修复，提交：
```bash
git add -A
git commit -m "fix: 端到端验证修复"
```
