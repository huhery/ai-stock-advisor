# AI 股票助手部署手册

## 目录

- [系统架构概览](#系统架构概览)
- [部署前置条件](#部署前置条件)
- [阿里云部署指南](#阿里云部署指南)
- [腾讯云部署指南](#腾讯云部署指南)
- [生产环境配置优化](#生产环境配置优化)
- [监控与运维](#监控与运维)
- [故障排查](#故障排查)
- [备份与恢复](#备份与恢复)

---

## 系统架构概览

### 技术栈

| 组件 | 技术选型 | 版本 |
|------|----------|------|
| 前端 | Vue 3 + Vite + Element Plus + ECharts | Node 20 |
| 后端 | Java + Spring Boot 2.7 + MyBatis Plus | JDK 8 |
| 数据服务 | Python 3.11 + FastAPI + AkShare | Python 3.11 |
| 数据库 | MySQL | 8.0 |
| 缓存 | Redis | 7.x |
| 大模型 | DeepSeek API | - |
| 容器编排 | Docker Compose | 3.8 |

### 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│                     (http://your-domain)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Nginx)                      │
│                       端口: 80/443                          │
└─────────────────────┬───────────────────────────────────────┘
                      │ /api/*
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Java 后端 (Spring Boot)                      │
│                       端口: 8080                            │
└───────┬─────────────────────────────────┬───────────────────┘
        │                                 │
        ▼                                 ▼
┌───────────────────┐         ┌───────────────────────────────┐
│   MySQL 8.0       │         │   Python 数据服务 (FastAPI)   │
│   端口: 3306      │         │        端口: 8001             │
│   存储: 业务数据   │         │   功能: 选股、爬虫、回测       │
└───────────────────┘         └───────────────┬───────────────┘
                                              │
                      ┌───────────────────────┤
                      │                       │
                      ▼                       ▼
            ┌─────────────────┐    ┌──────────────────┐
            │   Redis 7.x     │    │  DeepSeek API    │
            │   端口: 6379    │    │  (大模型服务)     │
            │   存储: 缓存     │    └──────────────────┘
            └─────────────────┘
```

### 端口映射

| 服务 | 容器端口 | 宿主机端口 | 协议 |
|------|----------|------------|------|
| Frontend (Nginx) | 80 | 80 | HTTP |
| Backend (Java) | 8080 | 8080 | HTTP |
| Data Service (Python) | 8001 | 8001 | HTTP |
| MySQL | 3306 | 3306 | TCP |
| Redis | 6379 | 6379 | TCP |

---

## 部署前置条件

### 服务器配置要求

#### 最低配置（测试环境）

| 资源 | 要求 |
|------|------|
| CPU | 2 核 |
| 内存 | 4 GB |
| 系统盘 | 40 GB SSD |
| 带宽 | 1 Mbps |

#### 推荐配置（生产环境）

| 资源 | 要求 |
|------|------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 系统盘 | 80 GB SSD |
| 数据盘 | 100 GB SSD（可选，用于 MySQL 数据持久化） |
| 带宽 | 5 Mbps |

### 操作系统

- **推荐**: Ubuntu 22.04 LTS / CentOS 8+ / Rocky Linux 8+
- **支持**: Debian 11+ / Alibaba Cloud Linux 3 / TencentOS 3.1

### 必需软件

| 软件 | 最低版本 | 安装命令 |
|------|----------|----------|
| Docker | 20.10+ | 见下方安装指南 |
| Docker Compose | 2.0+ | 见下方安装指南 |
| Git | 2.x | `apt install git` 或 `yum install git` |

---

## 阿里云部署指南

### 步骤 1: 购买云服务器

#### 1.1 登录阿里云控制台

访问 [阿里云 ECS 产品页](https://www.aliyun.com/product/ecs)

#### 1.2 选择配置

```
地域: 华东1（杭州）或 华北2（北京）[根据用户群体选择]
实例规格: ecs.c6.large (2 vCPU, 4 GiB) 测试环境
         或 ecs.c6.xlarge (4 vCPU, 8 GiB) 生产环境
镜像: Ubuntu 22.04 64位
存储: 系统盘 80 GB ESSD
网络: 专有网络 VPC，分配公网 IP
带宽: 按使用流量计费，5 Mbps
安全组: 放行 22, 80, 443 端口
```

#### 1.3 购买并启动实例

记录以下信息：
- 公网 IP 地址
- 实例 ID
- 登录密码（或 SSH 密钥）

### 步骤 2: 连接服务器

#### Windows 用户

```powershell
# 使用 PowerShell 或 Windows Terminal
ssh root@<your-server-ip>
```

#### Mac/Linux 用户

```bash
ssh root@<your-server-ip>
```

### 步骤 3: 安装 Docker

#### Ubuntu 22.04

```bash
# 更新软件包索引
apt update && apt upgrade -y

# 安装依赖
apt install -y ca-certificates curl gnupg lsb-release

# 添加 Docker 官方 GPG 密钥（使用阿里云镜像加速）
mkdir -p /etc/apt/keyrings
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 添加 Docker 软件源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 并设置开机自启
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
docker compose version
```

#### CentOS 8 / Rocky Linux 8

```bash
# 安装依赖
yum install -y yum-utils

# 添加 Docker 软件源（使用阿里云镜像）
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 安装 Docker
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 并设置开机自启
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
docker compose version
```

### 步骤 4: 配置 Docker 镜像加速（阿里云）

```bash
# 创建配置目录
mkdir -p /etc/docker

# 配置镜像加速器（使用阿里云镜像加速服务）
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://registry.cn-hangzhou.aliyuncs.com",
    "https://mirror.ccs.tencentyun.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# 重启 Docker 生效
systemctl daemon-reload
systemctl restart docker
```

### 步骤 5: 配置安全组

在阿里云控制台配置安全组规则：

| 方向 | 端口范围 | 协议 | 授权对象 | 说明 |
|------|----------|------|----------|------|
| 入方向 | 22 | TCP | 0.0.0.0/0 或指定 IP | SSH 登录 |
| 入方向 | 80 | TCP | 0.0.0.0/0 | HTTP |
| 入方向 | 443 | TCP | 0.0.0.0/0 | HTTPS |
| 入方向 | 3306 | TCP | 仅内网访问 | MySQL（可选） |

### 步骤 6: 上传项目代码

#### 方法 1: Git Clone（推荐）

```bash
# 创建工作目录
mkdir -p /opt/ai-stock-advisor
cd /opt

# 克隆项目（替换为您的仓库地址）
git clone https://github.com/your-username/ai-stock-advisor.git
cd ai-stock-advisor
```

#### 方法 2: SCP 上传

在本地电脑执行：

```bash
# 打包项目
cd e:\work\ai
tar -czf ai-stock-advisor.tar.gz ai-stock-advisor

# 上传到服务器
scp ai-stock-advisor.tar.gz root@<your-server-ip>:/opt/

# 在服务器上解压
ssh root@<your-server-ip>
cd /opt
tar -xzf ai-stock-advisor.tar.gz
cd ai-stock-advisor
```

### 步骤 7: 配置环境变量

```bash
cd /opt/ai-stock-advisor

# 创建环境变量文件
cat > .env << 'EOF'
# DeepSeek API 配置
LLM_API_KEY=sk-your-deepseek-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 数据库密码（生产环境请修改）
MYSQL_ROOT_PASSWORD=YourStrongPassword123!
MYSQL_DATABASE=ai_stock

# Redis 密码（可选）
# REDIS_PASSWORD=your-redis-password
EOF

# 设置文件权限
chmod 600 .env
```

### 步骤 8: 构建并启动服务

```bash
cd /opt/ai-stock-advisor

# 构建所有镜像
docker compose build

# 启动所有服务（后台运行）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 步骤 9: 验证部署

```bash
# 检查服务健康状态
curl http://localhost/api/
curl http://localhost:8001/
curl http://localhost:8080/api/

# 检查数据库连接
docker compose exec mysql mysql -uroot -p -e "SHOW DATABASES;"
```

### 步骤 10: 配置域名和 HTTPS（可选）

#### 10.1 域名解析

在阿里云域名控制台添加 A 记录：
- 主机记录: `@` 或 `www`
- 记录值: 服务器公网 IP

#### 10.2 申请 SSL 证书

```bash
# 安装 certbot
apt install -y certbot python3-certbot-nginx

# 申请证书（替换为您的域名）
certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# 证书路径
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

#### 10.3 配置 HTTPS

修改 `frontend/nginx.conf` 或创建新的 SSL 配置：

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 腾讯云部署指南

### 步骤 1: 购买云服务器

#### 1.1 登录腾讯云控制台

访问 [腾讯云 CVM 产品页](https://cloud.tencent.com/product/cvm)

#### 1.2 选择配置

```
地域: 广州 或 上海 [根据用户群体选择]
可用区: 随机分配
实例规格: S5.MEDIUM4 (2 vCPU, 4 GiB) 测试环境
         或 S5.LARGE8 (4 vCPU, 8 GiB) 生产环境
镜像: Ubuntu 22.04 LTS 64位
系统盘: 80 GB SSD 云硬盘
网络: 默认 VPC，分配公网 IP
带宽: 按使用流量计费，5 Mbps
安全组: 放行 22, 80, 443 端口
```

### 步骤 2: 安装 Docker

#### Ubuntu 22.04

```bash
# 更新软件包
apt update && apt upgrade -y

# 安装依赖
apt install -y ca-certificates curl gnupg lsb-release

# 添加 Docker GPG 密钥（使用腾讯云镜像）
mkdir -p /etc/apt/keyrings
curl -fsSL https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 添加软件源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动并设置开机自启
systemctl start docker
systemctl enable docker

# 验证
docker --version
docker compose version
```

### 步骤 3: 配置镜像加速（腾讯云）

```bash
mkdir -p /etc/docker

cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.cn-hangzhou.aliyuncs.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

systemctl daemon-reload
systemctl restart docker
```

### 步骤 4: 配置安全组

在腾讯云控制台配置安全组：

| 类型 | 来源 | 协议端口 | 策略 | 说明 |
|------|------|----------|------|------|
| 自定义 | 0.0.0.0/0 | TCP:22 | 允许 | SSH |
| 自定义 | 0.0.0.0/0 | TCP:80 | 允许 | HTTP |
| 自定义 | 0.0.0.0/0 | TCP:443 | 允许 | HTTPS |

### 步骤 5: 部署应用

后续步骤与阿里云部署相同：

```bash
# 上传代码
cd /opt
git clone https://github.com/your-username/ai-stock-advisor.git
cd ai-stock-advisor

# 配置环境变量
cat > .env << 'EOF'
LLM_API_KEY=sk-your-deepseek-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
MYSQL_ROOT_PASSWORD=YourStrongPassword123!
EOF

# 构建并启动
docker compose build
docker compose up -d

# 验证
docker compose ps
```

---

## 生产环境配置优化

### 数据库配置优化

#### MySQL 配置调优

创建自定义 MySQL 配置文件：

```bash
mkdir -p /opt/ai-stock-advisor/mysql/conf.d

cat > /opt/ai-stock-advisor/mysql/conf.d/my.cnf << 'EOF'
[mysqld]
# 基础配置
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
default-time-zone = '+08:00'

# 性能配置（8GB 内存服务器）
innodb_buffer_pool_size = 2G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# 连接配置
max_connections = 200
wait_timeout = 600
interactive_timeout = 600

# 慢查询日志
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2

# 二进制日志（用于主从复制和时间点恢复）
log_bin = mysql-bin
binlog_format = ROW
expire_logs_days = 7
EOF
```

修改 `docker-compose.yml`：

```yaml
mysql:
  image: mysql:8.0
  volumes:
    - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    - mysql_data:/var/lib/mysql
    - ./mysql/conf.d:/etc/mysql/conf.d  # 添加自定义配置
```

#### Redis 配置

```bash
mkdir -p /opt/ai-stock-advisor/redis

cat > /opt/ai-stock-advisor/redis/redis.conf << 'EOF'
# 内存配置
maxmemory 1gb
maxmemory-policy allkeys-lru

# 持久化
appendonly yes
appendfsync everysec

# 密码（生产环境强烈建议设置）
# requirepass YourRedisPassword123!

# 日志
loglevel notice
EOF
```

修改 `docker-compose.yml`：

```yaml
redis:
  image: redis:7-alpine
  command: redis-server /etc/redis/redis.conf
  volumes:
    - ./redis/redis.conf:/etc/redis/redis.conf
    - redis_data:/data
```

### Java 应用优化

#### JVM 参数调优

修改 `backend/Dockerfile`：

```dockerfile
FROM openjdk:8-jre-slim
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar

# JVM 参数
ENV JAVA_OPTS="-Xms512m -Xmx1024m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/logs"

EXPOSE 8080
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
```

### 数据服务优化

#### Gunicorn 多进程

修改 `data-service/Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Gunicorn
RUN pip install gunicorn

COPY app/ ./app/

EXPOSE 8001

# 使用 Gunicorn 运行（4 个工作进程）
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8001"]
```

### 数据持久化与备份

#### 添加数据卷挂载

更新 `docker-compose.yml`：

```yaml
services:
  mysql:
    volumes:
      - mysql_data:/var/lib/mysql
      - ./backup:/backup  # 备份目录

  redis:
    volumes:
      - redis_data:/data

volumes:
  mysql_data:
    driver: local
  redis_data:
    driver: local
```

#### 自动备份脚本

```bash
cat > /opt/ai-stock-advisor/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/ai-stock-advisor/backup"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# MySQL 备份
docker compose exec -T mysql mysqldump -uroot -p${MYSQL_ROOT_PASSWORD} ai_stock > $BACKUP_DIR/ai_stock_$DATE.sql

# 压缩备份
gzip $BACKUP_DIR/ai_stock_$DATE.sql

# 删除 7 天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ai_stock_$DATE.sql.gz"
EOF

chmod +x /opt/ai-stock-advisor/scripts/backup.sh
```

#### 添加定时任务

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点执行备份
0 2 * * * /opt/ai-stock-advisor/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 监控与运维

### 容器状态监控

```bash
# 查看所有容器状态
docker compose ps

# 查看资源使用
docker stats

# 查看日志
docker compose logs -f --tail=100

# 查看特定服务日志
docker compose logs -f backend
docker compose logs -f data-service
```

### 健康检查脚本

```bash
cat > /opt/ai-stock-advisor/scripts/health-check.sh << 'EOF'
#!/bin/bash

services=("backend" "data-service" "mysql" "redis")
alert=""

for service in "${services[@]}"; do
    status=$(docker compose ps -q $service 2>/dev/null | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null)
    if [ "$status" != "running" ]; then
        alert="$alert\n$service is not running (status: $status)"
    fi
done

if [ -n "$alert" ]; then
    echo -e "Alert:$alert"
    # 可选：发送告警通知
    # curl -X POST "https://your-webhook-url" -d "text=$alert"
    exit 1
else
    echo "All services are healthy"
    exit 0
fi
EOF

chmod +x /opt/ai-stock-advisor/scripts/health-check.sh
```

### 日志轮转

Docker 日志已配置轮转（见 daemon.json），确保日志不会占用过多磁盘空间。

### 服务重启

```bash
# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart backend

# 完全重新部署
docker compose down
docker compose up -d --build
```

---

## 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 查看错误日志
docker compose logs backend

# 常见原因：
# - 数据库未就绪：等待 MySQL 完全启动
# - 端口冲突：检查端口占用
# - 环境变量错误：检查 .env 文件
```

#### 2. 数据库连接失败

```bash
# 检查 MySQL 状态
docker compose exec mysql mysqladmin ping -h localhost

# 检查用户权限
docker compose exec mysql mysql -uroot -p -e "SHOW GRANTS;"

# 测试连接
docker compose exec backend ping mysql
```

#### 3. 大模型 API 调用失败

```bash
# 检查 API Key 是否正确
docker compose exec backend env | grep LLM

# 测试 API 连通性
docker compose exec backend curl -I https://api.deepseek.com
```

#### 4. 前端页面无法访问

```bash
# 检查 Nginx 配置
docker compose exec frontend nginx -t

# 检查前端容器日志
docker compose logs frontend
```

### 性能问题排查

```bash
# 查看容器资源使用
docker stats --no-stream

# 查看系统资源
htop
df -h
free -m

# MySQL 慢查询分析
docker compose exec mysql mysqldumpslow -s t /var/log/mysql/slow.log
```

---

## 备份与恢复

### 完整备份

```bash
#!/bin/bash
# complete-backup.sh

BACKUP_DIR="/opt/backup"
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR="/opt/ai-stock-advisor"

mkdir -p $BACKUP_DIR

# 1. 数据库备份
docker compose exec -T mysql mysqldump -uroot -p${MYSQL_ROOT_PASSWORD} --all-databases > $BACKUP_DIR/mysql_$DATE.sql

# 2. Redis 备份
docker compose exec redis redis-cli BGSAVE
docker compose cp redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 3. 配置文件备份
tar -czf $BACKUP_DIR/config_$DATE.tar.gz $PROJECT_DIR/.env $PROJECT_DIR/docker-compose.yml

# 4. 打包所有备份
tar -czf $BACKUP_DIR/complete_backup_$DATE.tar.gz -C $BACKUP_DIR mysql_$DATE.sql redis_$DATE.rdb config_$DATE.tar.gz

# 清理临时文件
rm $BACKUP_DIR/mysql_$DATE.sql $BACKUP_DIR/redis_$DATE.rdb $BACKUP_DIR/config_$DATE.tar.gz

echo "Complete backup saved to: $BACKUP_DIR/complete_backup_$DATE.tar.gz"
```

### 恢复

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1
BACKUP_DIR="/tmp/restore_$$"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore.sh <backup-file.tar.gz>"
    exit 1
fi

# 解压备份
mkdir -p $BACKUP_DIR
tar -xzf $BACKUP_FILE -C $BACKUP_DIR

# 停止服务
docker compose stop backend data-service

# 恢复数据库
docker compose exec -T mysql mysql -uroot -p${MYSQL_ROOT_PASSWORD} < $BACKUP_DIR/mysql_*.sql

# 恢复 Redis
docker compose cp $BACKUP_DIR/redis_*.rdb redis:/data/dump.rdb

# 重启服务
docker compose restart

# 清理
rm -rf $BACKUP_DIR

echo "Restore completed"
```

---

## 快速命令参考

```bash
# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 重新构建并启动
docker compose up -d --build

# 进入容器
docker compose exec backend bash
docker compose exec mysql bash

# 查看容器状态
docker compose ps

# 查看资源使用
docker stats

# 清理未使用的资源
docker system prune -af
```

---

## 联系与支持

- **项目地址**: https://github.com/your-username/ai-stock-advisor
- **问题反馈**: 请提交 GitHub Issue

---

## 附录

### A. DeepSeek API 获取

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册/登录账号
3. 创建 API Key
4. 复制 API Key 到 `.env` 文件

### B. 常用配置模板

#### 生产环境 docker-compose.yml（完整版）

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: ai-stock-mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ai_stock
      TZ: Asia/Shanghai
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./mysql/conf.d:/etc/mysql/conf.d
      - ./backup:/backup
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: ai-stock-redis
    restart: always
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  data-service:
    build:
      context: ./data-service
      dockerfile: Dockerfile
    container_name: ai-stock-data-service
    restart: always
    ports:
      - "8001:8001"
    environment:
      MYSQL_HOST: mysql
      REDIS_HOST: redis
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_BASE_URL: ${LLM_BASE_URL:-https://api.deepseek.com/v1}
      LLM_MODEL: ${LLM_MODEL:-deepseek-chat}
    depends_on:
      mysql:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ai-stock-backend
    restart: always
    ports:
      - "8080:8080"
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/ai_stock?useUnicode=true&characterEncoding=utf8mb4&serverTimezone=Asia/Shanghai
      SPRING_DATASOURCE_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      SPRING_REDIS_HOST: redis
      ADVISOR_DATA_SERVICE_URL: http://data-service:8001
      LLM_API_KEY: ${LLM_API_KEY}
      JAVA_OPTS: -Xms512m -Xmx1024m -XX:+UseG1GC
    depends_on:
      mysql:
        condition: service_healthy
      data-service:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ai-stock-frontend
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  mysql_data:
    driver: local
  redis_data:
    driver: local
```

---

**文档版本**: 1.0.0  
**最后更新**: 2026-06-05
