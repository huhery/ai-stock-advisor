# AI 股票顾问（AI Stock Advisor）

基于 AI 的 A 股智能选股系统，集成多维度量化分析、Kronos 深度学习价格预测、国际新闻情绪分析和遗传算法自动进化策略。

## 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [技术栈](#技术栈)
- [本地部署](#本地部署)
- [每日使用](#每日使用)
- [功能详解](#功能详解)
- [API 接口](#api-接口)
- [配置说明](#配置说明)
- [数据库结构](#数据库结构)
- [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端（Vue 3 + Element Plus）              │
│   选股推荐 │ AI 对话 │ 新闻资讯 │ 规则管理 │ 回测进化 │ 仪表盘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (port 80)
┌──────────────────────────▼──────────────────────────────────┐
│               Java 后端（Spring Boot）port 8080              │
│           路由转发 │ AI 对话 │ 认证（预留）                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (port 8001)
┌──────────────────────────▼──────────────────────────────────┐
│            Python 数据服务（FastAPI）port 8001                │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 选股引擎  │ │ 新闻爬虫  │ │ 自学习    │ │ Kronos AI预测  │  │
│  │ 4轮筛选   │ │ 8个数据源 │ │ 遗传进化   │ │ 价格预测模型   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────────┐
    │  MySQL   │    │  Redis   │    │ NVIDIA NIM   │
    │ 数据存储  │    │  缓存    │    │ LLM API     │
    └──────────┘    └──────────┘    └──────────────┘
```

---

## 核心功能

### 1. 智能选股（每日）
- 从全 A 股 4380+ 只股票中，经过 4 轮筛选，推荐 Top 10
- 第一轮：批量获取实时行情（秒级）
- 第二轮：量价快速过滤，排除垃圾股（秒级）
- 第三轮：K 线技术面精细打分（200 只，约 1 分钟）
- 第四轮：Kronos AI 深度学习价格预测加分

### 2. Kronos AI 价格预测
- 基于 Kronos 金融 K 线基础模型（4.1M/102M 参数）
- 输入最近 60 天日 K 线，预测未来 5 天走势
- 预测得分以 1.5 倍权重加入选股总分

### 3. 国际新闻情绪分析
- 爬取 8 个数据源：国务院、证监会、央行、Reuters、CNBC、SCMP、Investing、美联储
- 调用 LLM（NVIDIA NIM）分析新闻对 A 股板块的影响
- 提取关键词和受益板块，融入选股打分

### 4. 自动进化策略
- 遗传算法回测优化（6 个历史时期：牛市/熊市/震荡市）
- 每周自动进化：回测 → 对比基线 → 应用最优 → AI 分析失败案例
- 实盘数据反馈：根据推荐 T+5 表现自动调整规则权重
- AI 建议新规则：LLM 分析亏损案例，自动补充风控规则

### 5. AI 投资顾问对话
- 结合实时行情、政策新闻、选股结果进行对话
- 提供专业的投资分析和建议

### 6. 买卖信号管理
- 自动计算支撑位/压力位
- 动态止盈止损价格
- 持仓跟踪和卖出信号检测

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus + Vite | 响应式 Web UI |
| 后端 | Spring Boot 3 + MyBatis Plus | API 路由、AI 对话 |
| 数据服务 | Python FastAPI + APScheduler | 选股引擎、爬虫、进化 |
| AI 预测 | Kronos (PyTorch) | 金融 K 线基础模型 |
| LLM | NVIDIA NIM API (Llama 3.1 70B) | 新闻分析、规则建议 |
| 数据库 | MySQL 8.0 | 持久化存储 |
| 缓存 | Redis 7 | 会话、热数据 |
| 部署 | Docker Compose | 一键部署 |

---

## 本地部署

### 环境要求

- Python 3.10+（推荐 3.12）
- Java 17+
- Node.js 18+
- MySQL 8.0
- Redis（可选）

### 快速开始

#### 1. 安装 Python 依赖

```bash
cd data-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. 安装 Kronos 模型

```bash
cd data-service
git clone https://github.com/shiyu-coder/Kronos.git vendor/kronos
pip install torch einops huggingface_hub safetensors
```

#### 3. 配置环境变量

```bash
# Windows CMD（永久生效）
setx LLM_API_KEY "nvapi-你的NVIDIA密钥"

# 或临时设置
set LLM_API_KEY=nvapi-你的NVIDIA密钥
```

NVIDIA API 密钥获取：https://build.nvidia.com

#### 4. 初始化数据库

确保 MySQL 运行中，执行 `sql/init.sql` 初始化表结构和预置规则。

#### 5. 启动服务

```bash
# 启动数据服务
cd data-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 启动后端（另一个终端）
cd backend
mvn spring-boot:run

# 启动前端（另一个终端）
cd frontend
npm install
npm run dev
```

#### Docker 一键部署

```bash
docker-compose up -d
```

---

## 每日使用

### 方式一：双击脚本（推荐）

在 `data-service/` 目录下：

| 脚本 | 用途 | 频率 |
|------|------|------|
| `daily_run.bat` | 爬新闻→选股→跟踪→检查卖出 | 每天收盘后 |
| `weekly_evolve.bat` | 完整策略进化流程 | 每周末 |

### 方式二：API 调用

```bash
# 手动选股
curl -X POST http://localhost:8001/api/screening/run

# 手动爬虫
curl -X POST http://localhost:8001/api/news/crawl

# 手动进化
curl -X POST http://localhost:8001/api/evolution/run

# 查看今日推荐
curl http://localhost:8001/api/screening/today
```

### 方式三：Web 界面

打开浏览器访问 `http://localhost` 或 `http://localhost:5173`（dev 模式）

---

## 功能详解

### 选股引擎 4 轮筛选流程

```
全 A 股 4380 只
    │
    ▼ 第一轮：批量获取实时行情（腾讯 HTTP 接口）
4380 只有效行情
    │
    ▼ 第二轮：量价快速过滤
    │  - 价格 3~300 元
    │  - 排除 ST、涨停、跌停
    │  - 成交额 > 5000 万
    │  - PE 0~200
    │  - 当日跌幅 < 5%
~800 只
    │
    ▼ 第二轮半：活跃度排序取前 200
    │  - 涨幅 1~5% 加分
    │  - 成交额越大加分
200 只
    │
    ▼ 第三轮：K 线技术面精细打分
    │  - MA5 上穿 MA20（金叉）
    │  - MACD 金叉
    │  - 放量突破
    │  - PE 合理
    │  - 政策新闻关联
~60 只（评分>50）
    │
    ▼ 第四轮：Kronos AI 价格预测
    │  - 预测未来 5 天走势
    │  - 预测得分×1.5 权重加入总分
    │
    ▼ 排序取 Top 10
10 只推荐
```

### 自动进化机制

```
每周六 2:00 自动执行：

Step 1: 补充 K 线缓存（腾讯 HTTP 接口）
Step 2: 获取当前策略实盘基线（最近 30 天胜率/收益）
Step 3: 遗传算法进化（30 代，6 个历史时期回测）
Step 4: 评估对比
         ├── 进化结果 > 基线 → 自动应用新策略
         └── 进化结果 ≤ 基线 → 保持不变
Step 5: AI 分析失败案例 → 建议新规则 → 自动激活风控规则
```

### 预置筛选规则

| 规则 | 分类 | 默认权重 | 说明 |
|------|------|---------|------|
| 政策利好板块 | 政策 | 1.50 | 新闻关键词匹配股票名称/板块 |
| MA5上穿MA20 | 技术 | 1.00 | 短期趋势转多信号 |
| MACD金叉 | 技术 | 1.00 | 动能转正信号 |
| 放量突破 | 技术 | 1.20 | 量能配合的突破 |
| PE合理 | 基本面 | 0.80 | 估值偏低 |
| 营收增长 | 基本面 | 0.80 | 基本面成长性 |
| 主力净流入 | 资金 | 1.00 | 资金面向好 |
| 北向资金买入 | 资金 | 0.90 | 外资看好 |

规则权重会根据实盘表现和进化结果自动调整。

---

## API 接口

### 选股相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/screening/today | 获取今日推荐 |
| GET | /api/screening/history?date=YYYY-MM-DD | 获取历史推荐 |
| GET | /api/screening/dates | 获取有数据的日期列表 |
| GET | /api/screening/rules | 获取筛选规则 |
| POST | /api/screening/run | 手动触发选股 |

### 新闻相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/news/latest?limit=20 | 获取最新新闻 |
| GET | /api/news/search?keyword=xxx | 搜索新闻 |
| POST | /api/news/crawl | 手动触发爬虫 |

### 自学习相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tracking/performance | 推荐表现统计 |
| GET | /api/learning/suggestions | AI 建议的新规则 |
| POST | /api/learning/approve-rule?ruleId=N | 激活规则 |
| POST | /api/learning/reject-rule?ruleId=N | 拒绝规则 |
| POST | /api/learning/optimize | 手动触发权重优化 |

### 回测进化

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/backtest/run | 启动回测进化 |
| GET | /api/backtest/status | 查询进度 |
| POST | /api/backtest/apply | 应用最优结果 |
| GET | /api/backtest/history | 回测历史 |
| POST | /api/evolution/run | 完整自动进化 |
| GET | /api/evolution/log | 进化日志 |

### AI 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat/send | 发送消息 |
| GET | /api/chat/history?limit=50 | 对话历史 |

---

## 配置说明

### data-service/app/config.py

```python
MYSQL_HOST = '81.69.42.239'     # MySQL 地址
MYSQL_PORT = 3306               # MySQL 端口
MYSQL_USER = 'root'             # 用户名
MYSQL_PASSWORD = 'AiStock2026!' # 密码
MYSQL_DB = 'ai_stock'           # 数据库名

REDIS_HOST = 'localhost'        # Redis 地址
REDIS_PORT = 6379               # Redis 端口

LLM_API_KEY = ''                # NVIDIA NIM API 密钥
LLM_BASE_URL = 'https://integrate.api.nvidia.com/v1'  # LLM API 地址
LLM_MODEL = 'meta/llama-3.1-70b-instruct'             # 模型名称
```

所有配置都支持环境变量覆盖。

### 数据源接口（全部走 HTTP，不受代理影响）

| 数据 | 接口 | 协议 |
|------|------|------|
| 股票列表 | 新浪财经 | HTTP |
| 实时行情 | 腾讯财经 qt.gtimg.cn | HTTP |
| K 线数据 | 腾讯财经 web.ifzq.gtimg.cn | HTTP |
| 板块信息 | 东方财富 82.push2.eastmoney.com | HTTP |

---

## 数据库结构

| 表 | 说明 | 关键字段 |
|------|------|---------|
| policy_news | 新闻资讯 | source, title, keywords, related_sectors |
| stock_recommendation | 每日选股推荐 | stock_code, total_score, recommend_date, buy_price |
| recommendation_tracking | 推荐跟踪 | recommendation_id, days_after, change_pct |
| screening_rules | 筛选规则 | name, weight, win_rate, status |
| backtest_history | 回测进化历史 | win_rate, avg_return, best_weights |
| stock_kline_cache | K 线缓存 | stock_code, trade_date, OHLCV |
| chat_history | 对话历史 | role, content |
| evolution_log | 自动进化日志 | result, detail |

---

## 项目目录结构

```
ai-stock-advisor/
├── frontend/                # Vue 3 前端
│   └── src/views/           # 页面：选股、对话、新闻、规则、回测、仪表盘
├── backend/                 # Spring Boot 后端
│   └── src/main/java/com/advisor/
│       ├── controller/      # API 控制器
│       ├── client/          # LLM 客户端、数据服务客户端
│       └── config/          # 配置类
├── data-service/            # Python 数据服务（核心）
│   ├── app/
│   │   ├── screening/       # 选股引擎 + 卖出信号
│   │   ├── crawler/         # 新闻爬虫（8 个数据源）
│   │   ├── learning/        # 自学习：跟踪、优化、回测、自动进化
│   │   ├── prediction/      # Kronos AI 价格预测
│   │   ├── stock_data/      # 股票池、板块、K 线缓存
│   │   ├── config.py        # 配置
│   │   ├── db.py            # 数据库连接
│   │   └── main.py          # FastAPI 入口 + 定时任务
│   ├── vendor/kronos/       # Kronos 模型仓库
│   ├── daily_run.bat        # 每日手动执行脚本
│   └── weekly_evolve.bat    # 每周进化脚本
├── sql/init.sql             # 数据库初始化
├── deploy/                  # 生产部署配置
├── docker-compose.yml       # Docker 编排
└── scripts/                 # 工具脚本
```

---

## 常见问题

### Q: 为什么选股池显示只有 100 只？
A: 新浪接口可能暂时不可用，系统自动使用兜底池。检查网络后重启服务即可。

### Q: 板块显示为空？
A: 运行 `python fix_sectors.py` 补充已有记录的板块信息。新选股时会自动获取板块。

### Q: LLM 新闻分析没有执行？
A: 需要设置环境变量 `LLM_API_KEY`。没有新新闻入库时也不会触发分析。

### Q: 回测时报 SSL 错误？
A: 已修复。所有接口统一走 HTTP，不受代理/VPN 影响。

### Q: 怎么查看策略效果？
A: 运行 2 周以上后，访问 `/api/tracking/performance` 查看 T+5 胜率和平均收益。

### Q: 进化后策略变差了怎么办？
A: 系统设计了保护机制：只有进化结果显著优于当前基线才会应用，不会退步。

---

## 免责声明

本系统仅供学习和研究使用。股票市场存在风险，AI 选股结果仅供参考，不构成任何投资建议。投资者应独立判断并承担相应风险。

---

**版本**: 2.0.0  
**最后更新**: 2026-06-12
