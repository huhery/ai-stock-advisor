# AI 股票助手 - CentOS 8.5 一键部署包设计

## 概述

为 AI 股票助手项目生成一个 tar.gz 安装包，上传到腾讯云 CentOS 8.5 服务器后，用户编辑配置文件、运行 `install.sh` 即可完成全部部署。

**目标环境：** 腾讯云 CentOS 8.5，最低 2 核 4GB  
**部署方式：** 混合方案——包含源码，安装时联网安装 Docker 并在服务器上构建镜像  
**配置方式：** 用户预先编辑 `config.env` 文件

---

## 安装包结构

```
ai-stock-advisor-deploy.tar.gz
├── install.sh                    # 一键安装入口（root 运行）
├── config.env                    # 用户编辑的配置模板
├── scripts/
│   ├── start.sh                  # 启动所有服务
│   ├── stop.sh                   # 停止所有服务
│   ├── restart.sh                # 重启所有服务
│   ├── status.sh                 # 健康检查 + 状态展示
│   ├── backup.sh                 # MySQL 备份（gzip，保留 7 天）
│   ├── uninstall.sh              # 卸载（停容器、删镜像、删 systemd 服务）
│   └── ai-stock-advisor.service  # systemd 单元文件
├── docker-compose.prod.yml       # 生产环境编排文件
├── backend/                      # Java 后端（Dockerfile + pom.xml + src/）
├── data-service/                 # Python 数据服务（Dockerfile + requirements.txt + app/）
├── frontend/                     # 前端（Dockerfile + package.json + src/ + nginx.conf）
├── sql/
│   └── init.sql                  # 数据库初始化
├── mysql/
│   └── conf.d/my.cnf             # MySQL 生产调优配置
└── redis/
    └── redis.conf                # Redis 生产配置
```

---

## config.env 模板

```env
# === 必填 ===
LLM_API_KEY=sk-your-deepseek-api-key

# === 可选（有默认值）===
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
MYSQL_ROOT_PASSWORD=AiStock2026!
INSTALL_DIR=/opt/ai-stock-advisor
HTTP_PORT=80
```

---

## install.sh 执行流程

### 1. 前置检查

- 确认以 root 运行
- 检查 CentOS 版本（支持 8.x）
- 检查 `config.env` 存在且 `LLM_API_KEY` 已填写
- 检查磁盘空间（至少 20GB 可用）
- 检查端口未被占用（80, 8080, 8001, 3306, 6379）

### 2. 修复 CentOS 8 EOL 源

CentOS 8 已 EOL，默认 yum 源不可用。自动将 mirrorlist 切换为 vault.centos.org（幂等，已切换则跳过）。

### 3. 安装 Docker

- 安装依赖（yum-utils）
- 添加 Docker CE 仓库（阿里云镜像源）
- 安装 docker-ce + docker-ce-cli + containerd.io + docker-compose-plugin
- 配置镜像加速（腾讯云 + 阿里云双源）
- 启动 Docker 并 enable

### 4. 部署应用

- 将项目文件复制到 `INSTALL_DIR`（默认 `/opt/ai-stock-advisor`）
- 从 `config.env` 生成 `.env` 文件
- 执行 `docker compose -f docker-compose.prod.yml build`
- 执行 `docker compose -f docker-compose.prod.yml up -d`

### 5. 注册系统服务

- 复制 `ai-stock-advisor.service` 到 `/etc/systemd/system/`
- `systemctl daemon-reload && systemctl enable ai-stock-advisor`

### 6. 配置定时备份

- 添加 cron 任务：每天凌晨 2 点执行 `backup.sh`

### 7. 等待并验证

- 等待 MySQL 健康（最多 60 秒）
- curl 检查各服务端点（frontend:80, backend:8080, data-service:8001）
- 输出部署结果摘要

### 错误处理

- 每步执行后检查退出码，失败时打印具体错误信息并退出
- 脚本设计为幂等——已完成的步骤会跳过（Docker 已安装则跳过安装，服务已注册则跳过注册）
- 不做半成品回滚，用户可以看到哪一步失败了，修复后重新运行

---

## docker-compose.prod.yml

相比开发版 docker-compose.yml 的改动：

| 项目 | 开发版 | 生产版 |
|------|--------|--------|
| restart 策略 | 无 | always |
| container_name | 无 | 固定命名 ai-stock-* |
| MySQL 配置 | 默认 | 挂载 mysql/conf.d/my.cnf |
| MySQL 密码 | 硬编码 root123 | 从 .env 读取 |
| Redis 持久化 | 无 | appendonly + volume |
| data-service | uvicorn 单进程 | gunicorn 2 worker |
| backend JVM | 默认 | -Xms256m -Xmx512m -XX:+UseG1GC |
| 数据卷 | mysql_data | mysql_data + redis_data |

---

## 生产配置

### MySQL（mysql/conf.d/my.cnf）

- innodb_buffer_pool_size = 512M
- max_connections = 100
- slow_query_log = 1
- long_query_time = 2
- default-time-zone = '+08:00'
- character-set-server = utf8mb4

### Redis（redis/redis.conf）

- maxmemory 512mb
- maxmemory-policy allkeys-lru
- appendonly yes
- appendfsync everysec

---

## 运维脚本

| 脚本 | 功能 |
|------|------|
| start.sh | `docker compose -f docker-compose.prod.yml up -d` |
| stop.sh | `docker compose -f docker-compose.prod.yml down` |
| restart.sh | `docker compose -f docker-compose.prod.yml restart` |
| status.sh | 显示容器状态 + curl 各服务健康端点 |
| backup.sh | mysqldump → gzip，保留最近 7 天，存放于 `$INSTALL_DIR/backup/` |
| uninstall.sh | 停容器、删镜像、删 systemd 服务、删 cron。默认保留数据，`--purge` 参数删除数据卷和 INSTALL_DIR |

### systemd 服务（ai-stock-advisor.service）

- Type=oneshot + RemainAfterExit=yes
- ExecStart 执行 start.sh
- ExecStop 执行 stop.sh
- After=docker.service
- WantedBy=multi-user.target

---

## 打包流程

项目中新增 `deploy/pack.bat`（Windows 批处理），运行后生成 `deploy/output/ai-stock-advisor-deploy.tar.gz`。

打包内容：
- `backend/`（排除 target/）
- `data-service/`（排除 __pycache__/）
- `frontend/`（排除 node_modules/、dist/）
- `sql/`
- `deploy/` 中的 install.sh、config.env、scripts/、docker-compose.prod.yml、mysql/、redis/

---

## 用户操作流程

```bash
# 1. 上传安装包到服务器
scp ai-stock-advisor-deploy.tar.gz root@your-server:/tmp/

# 2. 解压
cd /tmp && tar -xzf ai-stock-advisor-deploy.tar.gz && cd ai-stock-advisor-deploy

# 3. 编辑配置
vi config.env   # 必填 LLM_API_KEY

# 4. 执行安装
bash install.sh
```

安装完成后管理命令：
```bash
systemctl start/stop/restart ai-stock-advisor
/opt/ai-stock-advisor/scripts/status.sh
/opt/ai-stock-advisor/scripts/backup.sh
```

---

## 项目文件位置

所有部署相关文件放在 `ai-stock-advisor/deploy/` 目录下：

```
ai-stock-advisor/
├── deploy/
│   ├── pack.bat
│   ├── install.sh
│   ├── config.env
│   ├── docker-compose.prod.yml
│   ├── mysql/conf.d/my.cnf
│   ├── redis/redis.conf
│   └── scripts/
│       ├── start.sh
│       ├── stop.sh
│       ├── restart.sh
│       ├── status.sh
│       ├── backup.sh
│       ├── uninstall.sh
│       └── ai-stock-advisor.service
├── backend/
├── data-service/
├── frontend/
├── sql/
└── ...
```

---

## 不包含的内容

- HTTPS/SSL 配置（用户按需自行配置，可参考 deployment-guide.md）
- 域名配置
- 监控告警（Prometheus/Grafana）
- 多节点部署
- CI/CD 流水线
