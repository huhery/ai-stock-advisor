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