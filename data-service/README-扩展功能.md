# AI股票顾问 - 扩展功能文档

## 已实现的扩展功能

### 1. 全A股选股范围扩展
**状态**: ✅ 已完成
**描述**: 从105只沪深300子集扩展到全A股（沪深主板+创业板）

**实现方案**:
- 实时从东方财富接口获取股票列表
- 排除ST股和科创板/北交所
- 兜底机制：接口失败时使用本地股票池（约100只核心股票）

**主要修改文件**:
- `app/stock_data/stock_pool.py`: 实时股票池获取
- `app/screening/engine.py`: 两轮筛选流程

**当前状态**:
- ✅ 代码结构完整
- ⚠️ 东方财富接口访问失败（网络限制）
- ✅ 兜底池已扩展至~100只核心股票

### 2. 国际新闻分析集成
**状态**: ✅ 已完成
**描述**: 集成国际财经新闻到选股流程中

**实现方案**:
- 爬取8个数据源（3个国内 + 5个国际）
- 使用LLM分析新闻对A股板块的影响
- 提取关键词和受益板块回填数据库

**主要修改文件**:
- `app/crawler/policy_crawler.py`: 国际新闻爬虫和LLM分析
- `app/screening/engine.py`: 新闻关键词查询和打分

**当前状态**:
- ✅ 数据源配置完整
- ✅ 爬虫模块结构正常
- ⚠️ 需要配置LLM_API_KEY环境变量
- ✅ 数据库已有33条新闻记录

### 3. Kronos AI价格预测模型集成
**状态**: ✅ 已完成
**描述**: 集成Kronos K线基础模型进行股价预测

**实现方案**:
- 在选股流程第二轮后加入Kronos预测
- 对候选股（几十到几百只）进行批量预测
- 预测得分以1.5倍权重加入总分

**主要修改文件**:
- `app/prediction/kronos_predictor.py`: Kronos模型封装
- `app/screening/engine.py`: 预测调用和得分融合
- `requirements.txt`: 添加依赖（torch, einops等）

**当前状态**:
- ✅ 模块导入成功
- ✅ vendor/kronos目录完整
- ✅ PyTorch 2.12.0已安装（CPU版本）
- ⚠️ 首次运行需下载模型权重（~10-400MB）

## 测试验证

运行测试脚本验证所有功能：
```bash
cd data-service
python test_extensions.py
```

## 下一步操作

### 1. 配置环境变量（必需）
```bash
# Windows (CMD)
set LLM_API_KEY=你的DeepSeek_API密钥

# Windows (PowerShell)
$env:LLM_API_KEY = "你的DeepSeek_API密钥"

# Linux/Mac
export LLM_API_KEY="你的DeepSeek_API密钥"
```

获取API密钥: https://platform.deepseek.com/api_keys

### 2. 运行测试
```bash
# 测试完整流程
python test_extensions.py

# 或使用配置脚本
setup_env.bat
```

### 3. 生产运行
```bash
# 运行新闻爬虫（需要LLM_API_KEY）
python -m app.crawler.policy_crawler

# 运行选股引擎
python -c "from app.screening.engine import run_screening; run_screening()"

# 查看今日推荐
python -c "from app.screening.engine import get_today_recommendations; import json; print(json.dumps(get_today_recommendations(), ensure_ascii=False, indent=2))"
```

## 故障排除

### 问题1: 东方财富接口无法访问
**现象**: "实时获取股票列表失败，使用兜底池"
**解决方案**:
1. 检查网络连接和代理设置
2. 使用兜底池（已扩展至100只核心股票）
3. 尝试使用其他数据源（需修改代码）

### 问题2: LLM_API_KEY未设置
**现象**: "未配置LLM_API_KEY，无法分析新闻影响"
**解决方案**:
1. 获取DeepSeek API密钥
2. 设置环境变量
3. 重启命令行窗口

### 问题3: Kronos模型下载慢
**现象**: 首次运行时下载模型权重超时
**解决方案**:
1. 确保网络可访问Hugging Face
2. 使用国内镜像（如HF Mirror）
3. 手动下载模型文件到vendor/kronos/model目录

### 问题4: 数据库连接失败
**现象**: "数据库连接失败"
**解决方案**:
1. 检查MySQL服务是否运行
2. 验证`deploy/config.env`中的数据库配置
3. 检查防火墙设置

## 文件结构

```
data-service/
├── app/
│   ├── crawler/
│   │   └── policy_crawler.py      # 新闻爬虫（国内+国际）
│   ├── prediction/
│   │   └── kronos_predictor.py    # Kronos价格预测
│   ├── screening/
│   │   └── engine.py              # 选股引擎（集成所有扩展）
│   └── stock_data/
│       └── stock_pool.py          # 全A股股票池
├── vendor/
│   └── kronos/                    # Kronos模型仓库
├── test_extensions.py             # 功能测试脚本
├── fix_network_issues.py         # 网络问题修复
├── setup_env.bat                  # 环境配置脚本
└── README-扩展功能.md             # 本文档
```

## 性能考虑

1. **Kronos预测效率**: 对候选股（几十到几百只）批量预测，GPU加速，预计2-5分钟完成
2. **网络请求**: 股票行情批量获取（每批50只），减少网络延迟
3. **LLM调用**: 新闻分析分批进行（每批20条），控制token用量

## 未来改进建议

1. 增加更多国际新闻源（Bloomberg, FT等）
2. 实现多语言新闻自动翻译
3. 添加模型缓存机制，减少重复下载
4. 支持GPU加速的Kronos推理
5. 实现股票池动态更新机制

---

**最后更新**: 2026年6月12日
**版本**: 1.0.0

### 4. 微淼财务自由选股模块
**状态**: ✅ 已完成
**描述**: 基于微淼商学院课程的价值投资方法论，从全A股中筛选符合"财务自由"标准的好公司

**核心理念**: 好公司 + 好价格 + 长期持有

**筛选流程**:
- **海选**: 连续5年 ROE>15% + 毛利率>30% + 现金含量>80% + 上市≥5年 + 连续分红≥5年
- **精选**: ROE>20% + 毛利率>40% + 现金含量>100% + 负债率<60% + 派息率>25%
- **估值判断**: 深证A股PE<20 且 个股PE<15 且 动态股息率>10年国债收益率 → 买入

**数据来源**:
- 深证A股PE: value500.com（微淼课程推荐）→ 东方财富 → 腾讯（多源降级）
- 财务数据: 东方财富证券API（年报数据）
- 股票池: 新浪/东方财富实时获取全A股

**主要文件**:
- `app/weimu/__init__.py`: 模块入口
- `app/weimu/screener.py`: 核心筛选引擎（海选→精选→估值三轮）
- `app/weimu/valuation.py`: 估值判断（PE+股息率 vs 国债收益率）+ 市场分析
- `app/weimu/allocation.py`: 资产配置建议（3-3-1工具体系）
- `app/weimu/evolution.py`: 自动进化引擎（LLM驱动规则更新）
- `app/weimu/runner.py`: 运行控制（同步/异步/快速模式）

**手动运行脚本**:
```bash
# 完整筛选（全A股扫描，耗时较长）
python run_weimu.py

# 快速模式（仅重算估值）
python run_weimu.py --quick

# 手动触发进化（分析政策+行情→更新规则）
python run_evolve.py
```

**API接口**:
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/weimu/run` | POST | 触发完整筛选（异步） |
| `/api/weimu/quick` | POST | 快速更新估值 |
| `/api/weimu/status` | GET | 查看筛选进度 |
| `/api/weimu/list` | GET | 获取选股结果 |
| `/api/weimu/history` | GET | 历史日期列表 |
| `/api/weimu/market-analysis` | GET | 市场PE估值分析 |
| `/api/weimu/allocation` | GET | 资产配置建议（可传capital参数） |
| `/api/weimu/evolve` | POST | 手动触发AI进化 |
| `/api/weimu/advice` | GET | 获取最新AI投资建议 |
| `/api/weimu/evolution-log` | GET | 进化历史日志 |

**前端页面** (`/freedom`):
- 📊 市场估值分析：大字展示当前深证A股PE + 估值水平 + 交易建议
- 💡 资产配置建议：输入资金金额，生成个性化3-3-1配置方案
- 🧬 AI进化建议：投资注意事项 + 风险警示 + 手动触发进化按钮
- 💰 财务自由选股：运行筛选 + 快速更新估值 + 精选结果表格

### 5. 自动进化系统（财务自由模块）
**状态**: ✅ 已完成
**描述**: 根据国家政策、市场行情自动更新投资理财规则

**进化信息源**:
1. 近期政策新闻（从已爬取的 policy_news 表中分析）
2. 当前市场环境（PE水平、利率环境、市场风格）
3. 上次筛选结果的实际表现
4. 公开渠道的价值投资最新实践（国九条、退市新规等）

**进化流程**:
```
收集市场环境 → 分析近期政策 → 评估历史表现
       ↓
LLM综合分析（或规则化降级）
       ↓
验证参数边界 → 应用调整 → 保存日志 + 更新建议
```

**安全机制**:
- 所有参数有边界限制（如ROE阈值只能在10%-30%之间调整）
- 核心理念永远不变：好公司+好价格+长期持有
- 所有变更记录日志，可追溯

**两种进化模式**:
- **有LLM**: 调用大模型综合分析，给出参数调整和投资建议
- **无LLM**: 规则化进化（利率变化→调门槛、市场高低估→调配置等确定性规则）

**定时任务**: 每周三 3:00 自动执行（需服务保持运行）

**手动执行**: `python run_evolve.py`（不依赖服务）

**2024-2026 市场适配更新**:
- 上市年限要求从3年提高到5年（注册制后IPO化妆更普遍）
- 新增低利率环境买入条件（国债<2%时，股息率>3%+PE<20也可买入）
- 资产配置增加公募C-REITs、中证红利ETF、同业存单指数基金等新工具
- 风险提示增加退市新规（面值退市加速、市值退市）

### 6. 资产配置建议系统
**状态**: ✅ 已完成
**描述**: 基于微淼课程"3-3-1工具"体系，根据市场PE动态生成个性化配置方案

**工具体系**:
- 三大核心工具: A股好公司、REITs（含公募C-REITs）、房地产
- 三个辅助工具: 国债逆回购、货币基金、债券/债券基金
- 一个保障工具: 保障型保险（定期寿险+重疾险+意外险）

**动态配置逻辑**:
| 市场PE | 股票配置 | 现金管理 | 策略 |
|--------|---------|---------|------|
| < 15 | 60% | 20% | 极度低估，激进买入 |
| 15-20 | 50% | 25% | 低估，积极配置 |
| 20-30 | 30% | 45% | 合理，等待为主 |
| 30-40 | 15% | 60% | 合理偏高，防御 |
| > 40 | 5% | 70% | 高估，全面防御 |

**示例**（20万，当前PE=16.54）:
- A股好公司: 50% = ¥8.5万（分3-5只，分三批买入）
- REITs: 15% = ¥2.55万（港股REITs/公募C-REITs）
- 逆回购: 15% = ¥2.55万（短期灵活，月末高收益）
- 货币基金: 10% = ¥1.7万（余额宝等随时可取）
- 债券: 10% = ¥1.7万（短债基金/国债）
- 另预留应急资金 ¥3万 + 保险 ¥3000/年

---

## 文件结构（更新）

```
data-service/
├── app/
│   ├── crawler/
│   │   ├── policy_crawler.py      # 新闻爬虫（国内+国际）
│   │   └── scrapling_client.py    # HTTP客户端（三层降级）
│   ├── learning/
│   │   ├── auto_evolution.py      # 选股策略自动进化
│   │   ├── backtester.py          # 遗传算法回测
│   │   ├── optimizer.py           # 规则权重优化
│   │   └── tracker.py             # 推荐表现跟踪
│   ├── prediction/
│   │   └── kronos_predictor.py    # Kronos价格预测
│   ├── screening/
│   │   ├── engine.py              # 每日选股引擎
│   │   ├── rules.py               # 选股规则实现
│   │   └── signals.py             # 买卖点信号
│   ├── stock_data/
│   │   ├── cache.py               # K线数据缓存
│   │   ├── finance_data.py        # 财务数据获取（东方财富）
│   │   ├── market_data.py         # 行情数据（AkShare）
│   │   ├── sector_map.py          # 板块映射
│   │   └── stock_pool.py          # 全A股股票池
│   ├── weimu/                     # 微淼财务自由模块（新增）
│   │   ├── __init__.py
│   │   ├── screener.py            # 核心筛选引擎
│   │   ├── valuation.py           # 估值判断 + 市场分析
│   │   ├── allocation.py          # 资产配置建议
│   │   ├── evolution.py           # 自动进化引擎
│   │   └── runner.py              # 运行控制
│   ├── config.py                  # 全局配置
│   ├── db.py                      # 数据库连接
│   └── main.py                    # FastAPI入口 + 定时任务
├── sql/
│   └── weimu_table.sql            # 微淼模块建表SQL
├── run_weimu.py                   # 手动选股脚本
├── run_evolve.py                  # 手动进化脚本
├── daily_run.bat                  # Windows每日定时脚本
├── requirements.txt
└── README-扩展功能.md             # 本文档
```

## 快速开始

### 1. 微淼财务自由选股
```bash
cd data-service

# 查看市场估值 + 运行选股
python run_weimu.py

# 仅刷新估值（秒级完成）
python run_weimu.py --quick
```

### 2. 手动进化（更新规则）
```bash
# 分析最新政策和行情，自动调整筛选参数
python run_evolve.py
```

### 3. 启动API服务
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 4. 定时任务（服务运行时自动执行）
| 时间 | 任务 |
|------|------|
| 每日 9:30 | 爬取新闻 |
| 每日 15:35 | 每日选股 |
| 每日 15:50 | 卖出信号检查 |
| 每日 16:00 | 跟踪推荐表现 |
| 每周三 3:00 | 微淼模块自动进化 |
| 每周六 2:00 | 选股策略遗传进化 |
| 每周日 20:00 | 规则权重微调 |
| 每周日 20:30 | AI建议新规则 |

## 未来改进建议

1. 增加更多国际新闻源（Bloomberg, FT等）
2. 实现多语言新闻自动翻译
3. 添加模型缓存机制，减少重复下载
4. 支持GPU加速的Kronos推理
5. 实现股票池动态更新机制
6. 微淼选股结果与每日选股结果交叉验证
7. 增加港股通REITs的自动筛选
8. 对接券商API实现模拟盘验证

---

**最后更新**: 2026年6月14日
**版本**: 2.0.0
