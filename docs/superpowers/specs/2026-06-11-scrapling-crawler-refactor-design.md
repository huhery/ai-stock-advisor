# Scrapling 爬虫改造设计文档

## 概述

将 AI Stock Advisor 项目中的两个数据获取模块（K 线数据预缓存、政策资讯爬虫）从失效的腾讯财经接口 + requests 库迁移到 Scrapling 框架，解决当前所有数据获取失败的问题。

## 背景

- `prefetch_local.py` 使用腾讯财经接口 (`web.ifzq.gtimg.cn`) 获取历史 K 线数据，该接口已失效
- `policy_crawler.py` 使用 `requests` 库爬取国务院/证监会/央行政策资讯，因 TLS 指纹被识别导致连接超时/拒绝
- 运行环境为本地 Windows 开发机

## 技术选型

### Scrapling 框架

选择 Scrapling（`pip install "scrapling[fetchers]"`）作为底层请求框架，原因：

1. **三级 Fetcher 架构**支持按需降级：
   - `Fetcher` — 快速 HTTP，可模拟浏览器 TLS 指纹（`impersonate='chrome'`）
   - `DynamicFetcher` — Playwright 浏览器自动化
   - `StealthyFetcher` — 完整反检测，绕过 Cloudflare Turnstile 等
2. 解决了 TLS 指纹被识别导致连接拒绝的核心问题
3. 支持 Session 管理，适合批量请求场景

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                  调用入口不变                          │
│  python scripts/prefetch_local.py --host ... --pool  │
│  定时任务 crawl_all_sources()                        │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
       ┌───────▼───────┐      ┌───────▼───────┐
       │ K线数据获取    │      │ 政策资讯爬取   │
       │ (prefetch)    │      │ (crawler)      │
       └───────┬───────┘      └───────┬───────┘
               │                      │
       ┌───────▼──────────────────────▼───────┐
       │       scrapling_client.py             │
       │  (统一封装 Fetcher 降级策略)           │
       │                                       │
       │  fetch_url(url) → str | None          │
       │  fetch_json(url) → dict | None        │
       │                                       │
       │  降级链:                               │
       │    Fetcher(chrome) → Fetcher(firefox)  │
       │    → StealthyFetcher                  │
       └───────────────────────────────────────┘
```

## 模块详细设计

### 1. scrapling_client.py（新增）

位置：`data-service/app/crawler/scrapling_client.py`

```python
def fetch_url(url, timeout=15, max_retries=2) -> str | None:
    """获取 URL 内容，返回 HTML 字符串"""

def fetch_json(url, timeout=15, max_retries=2) -> dict | None:
    """获取 URL 内容，返回解析后的 JSON dict"""
```

降级流程：
1. `Fetcher.get(url, impersonate='chrome', stealthy_headers=True, timeout=timeout)`
2. 失败 → `Fetcher.get(url, impersonate='firefox', stealthy_headers=True, timeout=timeout)`
3. 失败 → `StealthyFetcher.fetch(url, headless=True, network_idle=True)`
4. 失败 → 返回 `None`

### 2. K 线数据获取（双源兜底）

**数据源：**

| 优先级 | 数据源 | 接口 | 说明 |
|--------|--------|------|------|
| 1 | 东方财富 | `push2his.eastmoney.com/api/qt/stock/kline/get` | JSON API，结构化数据 |
| 2 | 新浪财经 | `money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData` | 备用兜底 |

**东方财富接口参数：**
- `secid`: 沪市 `1.{code}`，深市 `0.{code}`
- `klt=101`: 日 K 线
- `fqt=1`: 前复权
- `beg`/`end`: 起止日期（YYYYMMDD）
- `fields1=f1,f2,f3,f4,f5,f6`
- `fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61`

**新浪财经接口参数：**
- `symbol`: `sh600519`（沪）/ `sz000001`（深）
- `scale=240`: 日线
- `ma=no`
- `datalen=1000`

**请求流程（单只股票）：**
```
fetch_kline(stock_code, start_date, end_date):
  → 东方财富（Fetcher impersonate='chrome'）
    → 成功：解析 JSON，返回 K 线列表
    → 失败：切新浪财经
      → 成功：解析，返回
      → 失败：StealthyFetcher 重试东方财富
        → 成功/失败：记录结果
```

**返回格式（与原脚本兼容）：**
```python
[{'date': '2024-01-02', 'open': 1688.0, 'close': 1695.5, 'high': 1700.0, 'low': 1680.0, 'volume': 25000}, ...]
```

**命令行接口保持不变：**
```bash
python scripts/prefetch_local.py --host 81.69.42.239 --password AiStock2026! --pool all
```

### 3. 政策资讯爬虫（扩展国际源）

**数据源：**

| 类别 | 数据源 | URL | 反爬难度 | Fetcher 策略 |
|------|--------|-----|----------|-------------|
| 国内政策 | 国务院 | gov.cn/zhengce/zuixin/ | 低 | Fetcher |
| 国内政策 | 证监会 | csrc.gov.cn | 低 | Fetcher |
| 国内政策 | 央行 | pbc.gov.cn | 低 | Fetcher |
| 国际财经 | Reuters | reuters.com/business | 中 | Fetcher(impersonate) |
| 国际财经 | CNBC | cnbc.com/world | 中 | Fetcher(impersonate) |
| 中国市场 | SCMP | scmp.com/business | 中 | Fetcher(impersonate) |
| 市场数据 | Investing.com | investing.com/news | 高 | StealthyFetcher |
| 美联储 | Federal Reserve | federalreserve.gov/newsevents | 低 | Fetcher |

**统一返回格式：**
```python
{
    'source': 'Reuters',
    'title': '...',
    'url': '...',
    'publish_time': datetime,
    'category': 'international',  # domestic / international / fed
    'language': 'en',             # zh / en
}
```

**数据库变更：**
```sql
ALTER TABLE policy_news ADD COLUMN category VARCHAR(20) DEFAULT 'domestic';
ALTER TABLE policy_news ADD COLUMN language VARCHAR(10) DEFAULT 'zh';
```

## 错误处理

### K 线获取
- 单只股票失败不影响其他股票
- 断点续传：已缓存股票自动跳过
- 请求间隔 3 秒
- 双源 + StealthyFetcher 三层兜底

### 政策资讯
- 单个数据源失败不影响其他源
- 国际源与国内源互相独立
- StealthyFetcher 超时 30 秒

### scrapling_client
- 捕获所有异常，统一返回 None
- 降级前打印日志
- StealthyFetcher 失败不再重试

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `data-service/app/crawler/scrapling_client.py` | Fetcher 降级封装 |
| 重写 | `scripts/prefetch_local.py` | 东方财富+新浪双源，底层用 scrapling_client |
| 修改 | `data-service/app/crawler/policy_crawler.py` | 替换 requests，新增国际源 |
| 修改 | `data-service/app/stock_data/cache.py` | 替换 _fetch_from_akshare |
| 修改 | `data-service/requirements.txt` | 新增 scrapling[fetchers] |
| 不动 | `data-service/app/main.py` | API 和定时任务不变 |
| 不动 | `data-service/app/stock_data/stock_pool.py` | 股票池不变 |
| 不动 | `data-service/app/stock_data/market_data.py` | 实时行情不在本次范围 |

## 安装步骤

```bash
pip install "scrapling[fetchers]"
scrapling install
```

## 不在本次范围

- `market_data.py` 实时行情（AkShare 的实时接口是独立问题）
- 后端 Java 代码
- 前端展示层
