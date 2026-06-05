# AI 股票助手

个人 AI 投资助手，实时监控国家政策资讯，自动选股并持续优化策略。

## 功能

- 实时政策监控（国务院、证监会、央行等）
- 智能对话（资深A股高手角色）
- 每日自动选股（多维度打分）
- 跟踪推荐表现 + 自学习优化

## 技术栈

- 前端：Vue 3 + Vite + Element Plus + ECharts
- 后端：Java 8 + Spring Boot 2.7 + MyBatis Plus
- 数据服务：Python 3.11 + FastAPI + AkShare
- 存储：MySQL 8 + Redis
- 大模型：DeepSeek API

## 快速启动

### 1. 启动基础设施

```bash
docker-compose up -d
```

### 2. 启动 Python 数据服务

```bash
cd data-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 3. 启动 Java 后端

```bash
cd backend
mvn spring-boot:run
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 生产部署（一键安装包）

### 生成安装包（Windows）

```bash
cd deploy
pack.bat
```

生成的 `deploy/output/ai-stock-advisor-deploy.tar.gz` 即为安装包。

### 服务器安装（CentOS 8.5）

```bash
# 上传并解压
tar -xzf ai-stock-advisor-deploy.tar.gz
cd ai-stock-advisor-deploy

# 编辑配置（必填 LLM_API_KEY）
vi config.env

# 一键安装
bash install.sh
```

### 运维命令

```bash
systemctl start/stop/restart ai-stock-advisor   # 服务管理
/opt/ai-stock-advisor/scripts/status.sh          # 健康检查
/opt/ai-stock-advisor/scripts/backup.sh          # 手动备份
/opt/ai-stock-advisor/scripts/uninstall.sh       # 卸载
```

## 配置

在 `backend/src/main/resources/application.yml` 中配置：
- 数据库连接
- Redis 连接
- 大模型 API Key

## 免责声明

本工具提供的选股建议仅供参考学习，不构成投资建议。投资有风险，入市需谨慎。
