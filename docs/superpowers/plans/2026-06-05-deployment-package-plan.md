# CentOS 8.5 一键部署包实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 生成一个 tar.gz 安装包，上传到腾讯云 CentOS 8.5 服务器后，编辑 config.env、运行 install.sh 即可完成全部部署。

**架构：** deploy/ 目录包含所有部署脚本和生产配置。pack.bat 在 Windows 上将源码和部署文件打包为 tar.gz。install.sh 在服务器上完成 Docker 安装、镜像构建、服务启动和 systemd 注册。

**技术栈：** Bash 脚本、Docker Compose、systemd、Windows batch

---

## 文件结构

以下文件将在 `ai-stock-advisor/deploy/` 目录下创建：

| 文件 | 职责 |
|------|------|
| `deploy/config.env` | 配置模板，用户填写 API Key 和密码 |
| `deploy/docker-compose.prod.yml` | 生产环境 Docker 编排文件 |
| `deploy/mysql/conf.d/my.cnf` | MySQL 生产调优配置 |
| `deploy/redis/redis.conf` | Redis 生产配置 |
| `deploy/install.sh` | 一键安装入口脚本 |
| `deploy/scripts/start.sh` | 启动服务 |
| `deploy/scripts/stop.sh` | 停止服务 |
| `deploy/scripts/restart.sh` | 重启服务 |
| `deploy/scripts/status.sh` | 健康检查 |
| `deploy/scripts/backup.sh` | 数据库备份 |
| `deploy/scripts/uninstall.sh` | 卸载清理 |
| `deploy/scripts/ai-stock-advisor.service` | systemd 单元文件 |
| `deploy/pack.bat` | Windows 打包脚本 |

---

### 任务 1：创建配置模板和生产环境配置文件

**文件：**
- 创建：`deploy/config.env`
- 创建：`deploy/mysql/conf.d/my.cnf`
- 创建：`deploy/redis/redis.conf`

- [ ] **步骤 1：创建 config.env**

```env
# AI 股票助手 - 部署配置
# 使用前请填写必填项

# === 必填 ===
LLM_API_KEY=sk-your-deepseek-api-key

# === 可选（有默认值）===
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
MYSQL_ROOT_PASSWORD=AiStock2026!
INSTALL_DIR=/opt/ai-stock-advisor
HTTP_PORT=80
```

- [ ] **步骤 2：创建 MySQL 生产配置**

创建 `deploy/mysql/conf.d/my.cnf`：

```ini
[mysqld]
# 基础配置
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
default-time-zone = '+08:00'

# 性能配置（4GB 内存服务器）
innodb_buffer_pool_size = 512M
innodb_log_file_size = 128M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# 连接配置
max_connections = 100
wait_timeout = 600
interactive_timeout = 600

# 慢查询日志
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```

- [ ] **步骤 3：创建 Redis 生产配置**

创建 `deploy/redis/redis.conf`：

```conf
# 内存配置
maxmemory 512mb
maxmemory-policy allkeys-lru

# 持久化
appendonly yes
appendfsync everysec

# 日志
loglevel notice
```

- [ ] **步骤 4：Commit**

```bash
git add deploy/config.env deploy/mysql/conf.d/my.cnf deploy/redis/redis.conf
git commit -m "feat(deploy): 添加配置模板和生产环境数据库/缓存配置"
```

---

### 任务 2：创建 docker-compose.prod.yml

**文件：**
- 创建：`deploy/docker-compose.prod.yml`

- [ ] **步骤 1：创建生产环境 compose 文件**

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
    command: redis-server /etc/redis/redis.conf
    ports:
      - "6379:6379"
    volumes:
      - ./redis/redis.conf:/etc/redis/redis.conf
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
      SPRING_DATASOURCE_USERNAME: root
      SPRING_DATASOURCE_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      SPRING_REDIS_HOST: redis
      ADVISOR_DATA_SERVICE_URL: http://data-service:8001
      LLM_API_KEY: ${LLM_API_KEY}
      JAVA_OPTS: "-Xms256m -Xmx512m -XX:+UseG1GC"
    depends_on:
      mysql:
        condition: service_healthy
      data-service:
        condition: service_started

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ai-stock-frontend
    restart: always
    ports:
      - "${HTTP_PORT:-80}:80"
    depends_on:
      - backend

volumes:
  mysql_data:
    driver: local
  redis_data:
    driver: local
```

- [ ] **步骤 2：Commit**

```bash
git add deploy/docker-compose.prod.yml
git commit -m "feat(deploy): 添加生产环境 docker-compose 编排文件"
```

---

### 任务 3：创建运维脚本

**文件：**
- 创建：`deploy/scripts/start.sh`
- 创建：`deploy/scripts/stop.sh`
- 创建：`deploy/scripts/restart.sh`
- 创建：`deploy/scripts/status.sh`
- 创建：`deploy/scripts/backup.sh`
- 创建：`deploy/scripts/uninstall.sh`
- 创建：`deploy/scripts/ai-stock-advisor.service`

- [ ] **步骤 1：创建 start.sh**

```bash
#!/bin/bash
# 启动 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在启动 AI 股票助手..."
docker compose -f docker-compose.prod.yml up -d
echo "启动完成。运行 scripts/status.sh 查看状态。"
```

- [ ] **步骤 2：创建 stop.sh**

```bash
#!/bin/bash
# 停止 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在停止 AI 股票助手..."
docker compose -f docker-compose.prod.yml down
echo "已停止。"
```

- [ ] **步骤 3：创建 restart.sh**

```bash
#!/bin/bash
# 重启 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在重启 AI 股票助手..."
docker compose -f docker-compose.prod.yml restart
echo "重启完成。"
```

- [ ] **步骤 4：创建 status.sh**

```bash
#!/bin/bash
# 检查 AI 股票助手服务状态

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "=== 容器状态 ==="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== 健康检查 ==="

check_service() {
    local name=$1
    local url=$2
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo "  ✓ $name 正常"
    else
        echo "  ✗ $name 不可达 ($url)"
    fi
}

check_service "前端 (Nginx)" "http://localhost:${HTTP_PORT:-80}/"
check_service "后端 (Java)" "http://localhost:8080/api/"
check_service "数据服务 (Python)" "http://localhost:8001/"

echo ""
echo "=== 资源使用 ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep ai-stock || true
```

- [ ] **步骤 5：创建 backup.sh**

```bash
#!/bin/bash
# MySQL 定时备份脚本
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

# 读取配置
if [ -f .env ]; then
    source .env
fi

BACKUP_DIR="$INSTALL_DIR/backup"
DATE=$(date +%Y%m%d_%H%M%S)
MYSQL_PASSWORD="${MYSQL_ROOT_PASSWORD:-AiStock2026!}"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 执行备份
echo "正在备份数据库..."
docker compose -f docker-compose.prod.yml exec -T mysql \
    mysqldump -uroot -p"$MYSQL_PASSWORD" ai_stock > "$BACKUP_DIR/ai_stock_$DATE.sql"

# 压缩
gzip "$BACKUP_DIR/ai_stock_$DATE.sql"

# 删除 7 天前的备份
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "备份完成: $BACKUP_DIR/ai_stock_$DATE.sql.gz"
```

- [ ] **步骤 6：创建 uninstall.sh**

```bash
#!/bin/bash
# 卸载 AI 股票助手
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

PURGE=false
if [ "$1" = "--purge" ]; then
    PURGE=true
fi

echo "=== 卸载 AI 股票助手 ==="

# 停止并删除容器
echo "停止服务..."
docker compose -f docker-compose.prod.yml down --rmi local 2>/dev/null || true

# 删除 systemd 服务
echo "移除 systemd 服务..."
systemctl stop ai-stock-advisor 2>/dev/null || true
systemctl disable ai-stock-advisor 2>/dev/null || true
rm -f /etc/systemd/system/ai-stock-advisor.service
systemctl daemon-reload

# 删除 cron 任务
echo "移除定时备份..."
crontab -l 2>/dev/null | grep -v "ai-stock-advisor" | crontab - 2>/dev/null || true

if [ "$PURGE" = true ]; then
    echo "删除数据卷..."
    docker volume rm ai-stock-advisor_mysql_data ai-stock-advisor_redis_data 2>/dev/null || true
    echo "删除安装目录..."
    rm -rf "$INSTALL_DIR"
    echo "已完全清除（含数据）。"
else
    echo "卸载完成。数据保留在 $INSTALL_DIR。"
    echo "如需彻底删除（含数据），运行: bash $0 --purge"
fi
```

- [ ] **步骤 7：创建 systemd 服务单元文件**

```ini
[Unit]
Description=AI Stock Advisor
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ai-stock-advisor
ExecStart=/opt/ai-stock-advisor/scripts/start.sh
ExecStop=/opt/ai-stock-advisor/scripts/stop.sh
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

- [ ] **步骤 8：Commit**

```bash
git add deploy/scripts/
git commit -m "feat(deploy): 添加运维脚本和 systemd 服务文件"
```

---

### 任务 4：创建 install.sh 安装脚本

**文件：**
- 创建：`deploy/install.sh`

- [ ] **步骤 1：创建 install.sh**

脚本核心逻辑：

```bash
#!/bin/bash
# AI 股票助手一键安装脚本
# 目标环境：CentOS 8.5
set -e

# ==================== 变量 ====================
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CONFIG_FILE="$SCRIPT_DIR/config.env"
LOG_FILE="/tmp/ai-stock-install.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

# ==================== 1. 前置检查 ====================
check_prerequisites() {
    log_info "执行前置检查..."

    # 检查 root
    if [ "$(id -u)" -ne 0 ]; then
        log_error "请以 root 用户运行此脚本"
        exit 1
    fi

    # 检查系统版本
    if [ -f /etc/centos-release ]; then
        local ver=$(cat /etc/centos-release | grep -oP '\d+' | head -1)
        if [ "$ver" -ne 8 ]; then
            log_error "此脚本仅支持 CentOS 8.x，当前为 CentOS $ver"
            exit 1
        fi
    else
        log_warn "无法确认 CentOS 版本，继续安装..."
    fi

    # 检查配置文件
    if [ ! -f "$CONFIG_FILE" ]; then
        log_error "配置文件不存在: $CONFIG_FILE"
        log_error "请先编辑 config.env 后再运行安装"
        exit 1
    fi

    # 读取配置
    source "$CONFIG_FILE"

    # 检查必填项
    if [ -z "$LLM_API_KEY" ] || [ "$LLM_API_KEY" = "sk-your-deepseek-api-key" ]; then
        log_error "请在 config.env 中填写有效的 LLM_API_KEY"
        exit 1
    fi

    # 设置默认值
    INSTALL_DIR="${INSTALL_DIR:-/opt/ai-stock-advisor}"
    HTTP_PORT="${HTTP_PORT:-80}"
    MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-AiStock2026!}"
    LLM_BASE_URL="${LLM_BASE_URL:-https://api.deepseek.com/v1}"
    LLM_MODEL="${LLM_MODEL:-deepseek-chat}"

    # 检查磁盘空间（至少 20GB）
    local available=$(df / --output=avail -BG | tail -1 | tr -d ' G')
    if [ "$available" -lt 20 ]; then
        log_error "磁盘空间不足，需要至少 20GB，当前可用 ${available}GB"
        exit 1
    fi

    # 检查端口占用
    local ports=("$HTTP_PORT" "8080" "8001" "3306" "6379")
    for port in "${ports[@]}"; do
        if ss -tlnp | grep -q ":$port "; then
            log_error "端口 $port 已被占用，请释放后重试"
            exit 1
        fi
    done

    log_info "前置检查通过"
}

# ==================== 2. 修复 CentOS 8 源 ====================
fix_centos_repos() {
    log_info "检查 yum 源..."

    # 检查是否需要修复（CentOS 8 EOL）
    if grep -q "mirrorlist.centos.org" /etc/yum.repos.d/CentOS-*.repo 2>/dev/null; then
        log_info "修复 CentOS 8 EOL 源..."
        sed -i 's/mirrorlist=/#mirrorlist=/g' /etc/yum.repos.d/CentOS-*.repo
        sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*.repo
        yum clean all > /dev/null 2>&1
        log_info "yum 源已修复"
    else
        log_info "yum 源正常，跳过修复"
    fi
}

# ==================== 3. 安装 Docker ====================
install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker 已安装，跳过"
        return
    fi

    log_info "安装 Docker..."

    # 安装依赖
    yum install -y yum-utils >> "$LOG_FILE" 2>&1

    # 添加 Docker 仓库（阿里云镜像）
    yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo >> "$LOG_FILE" 2>&1

    # 安装 Docker
    yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin >> "$LOG_FILE" 2>&1

    # 配置镜像加速
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'DAEMON_EOF'
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
DAEMON_EOF

    # 启动 Docker
    systemctl daemon-reload
    systemctl start docker
    systemctl enable docker

    log_info "Docker 安装完成: $(docker --version)"
}

# ==================== 4. 部署应用 ====================
deploy_application() {
    log_info "部署应用到 $INSTALL_DIR..."

    # 创建安装目录
    mkdir -p "$INSTALL_DIR"

    # 复制文件（如果不是已经在目标目录）
    if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
        cp -r "$SCRIPT_DIR/backend" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/data-service" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/frontend" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/sql" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/mysql" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/redis" "$INSTALL_DIR/"
        cp -r "$SCRIPT_DIR/scripts" "$INSTALL_DIR/"
        cp "$SCRIPT_DIR/docker-compose.prod.yml" "$INSTALL_DIR/"
    fi

    # 生成 .env 文件
    cat > "$INSTALL_DIR/.env" << ENV_EOF
LLM_API_KEY=$LLM_API_KEY
LLM_BASE_URL=$LLM_BASE_URL
LLM_MODEL=$LLM_MODEL
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
HTTP_PORT=$HTTP_PORT
ENV_EOF
    chmod 600 "$INSTALL_DIR/.env"

    # 修正 systemd 服务中的路径
    sed -i "s|/opt/ai-stock-advisor|$INSTALL_DIR|g" "$INSTALL_DIR/scripts/ai-stock-advisor.service"

    # 设置脚本可执行权限
    chmod +x "$INSTALL_DIR/scripts/"*.sh

    # 构建镜像
    log_info "构建 Docker 镜像（首次可能需要 10-20 分钟）..."
    cd "$INSTALL_DIR"
    docker compose -f docker-compose.prod.yml build >> "$LOG_FILE" 2>&1

    # 启动服务
    log_info "启动服务..."
    docker compose -f docker-compose.prod.yml up -d >> "$LOG_FILE" 2>&1

    log_info "服务已启动"
}

# ==================== 5. 注册 systemd 服务 ====================
register_systemd() {
    log_info "注册 systemd 服务..."

    cp "$INSTALL_DIR/scripts/ai-stock-advisor.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable ai-stock-advisor

    log_info "systemd 服务已注册（开机自启已启用）"
}

# ==================== 6. 配置定时备份 ====================
setup_backup_cron() {
    log_info "配置定时备份..."

    # 创建备份目录
    mkdir -p "$INSTALL_DIR/backup"

    # 添加 cron（幂等：先删除旧的再添加）
    (crontab -l 2>/dev/null | grep -v "ai-stock-advisor"; echo "0 2 * * * $INSTALL_DIR/scripts/backup.sh >> /var/log/ai-stock-backup.log 2>&1") | crontab -

    log_info "每日凌晨 2 点自动备份已配置"
}

# ==================== 7. 验证部署 ====================
verify_deployment() {
    log_info "等待服务就绪..."

    # 等待 MySQL 健康
    local retries=60
    while [ $retries -gt 0 ]; do
        if docker compose -f docker-compose.prod.yml exec -T mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
            break
        fi
        retries=$((retries - 1))
        sleep 1
    done

    if [ $retries -eq 0 ]; then
        log_warn "MySQL 启动超时，请稍后手动检查"
    fi

    # 等待后端服务启动（最多 30 秒）
    sleep 10

    echo ""
    echo "==========================================="
    echo "    AI 股票助手部署完成"
    echo "==========================================="
    echo ""
    echo "  访问地址: http://$(hostname -I | awk '{print $1}'):$HTTP_PORT"
    echo ""
    echo "  管理命令:"
    echo "    systemctl start/stop/restart ai-stock-advisor"
    echo "    $INSTALL_DIR/scripts/status.sh"
    echo "    $INSTALL_DIR/scripts/backup.sh"
    echo ""
    echo "  日志查看:"
    echo "    cd $INSTALL_DIR && docker compose -f docker-compose.prod.yml logs -f"
    echo ""
    echo "  安装日志: $LOG_FILE"
    echo "==========================================="
}

# ==================== 主流程 ====================
main() {
    echo ""
    echo "==========================================="
    echo "    AI 股票助手 - 一键安装"
    echo "==========================================="
    echo ""

    check_prerequisites
    fix_centos_repos
    install_docker
    deploy_application
    register_systemd
    setup_backup_cron
    verify_deployment
}

main "$@"
```

- [ ] **步骤 2：Commit**

```bash
git add deploy/install.sh
git commit -m "feat(deploy): 添加一键安装脚本"
```

---

### 任务 5：创建 Windows 打包脚本

**文件：**
- 创建：`deploy/pack.bat`

- [ ] **步骤 1：创建 pack.bat**

```batch
@echo off
chcp 65001 >nul
echo ===================================
echo  AI 股票助手 - 打包部署安装包
echo ===================================
echo.

set "PROJECT_DIR=%~dp0.."
set "OUTPUT_DIR=%~dp0output"
set "TEMP_DIR=%TEMP%\ai-stock-advisor-deploy"
set "ARCHIVE_NAME=ai-stock-advisor-deploy.tar.gz"

:: 清理临时目录
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

echo [1/5] 复制部署文件...
xcopy "%~dp0install.sh" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0config.env" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0docker-compose.prod.yml" "%TEMP_DIR%\" /Y /Q >nul
xcopy "%~dp0scripts" "%TEMP_DIR%\scripts\" /E /Y /Q >nul
xcopy "%~dp0mysql" "%TEMP_DIR%\mysql\" /E /Y /Q >nul
xcopy "%~dp0redis" "%TEMP_DIR%\redis\" /E /Y /Q >nul

echo [2/5] 复制后端源码...
xcopy "%PROJECT_DIR%\backend\Dockerfile" "%TEMP_DIR%\backend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\backend\pom.xml" "%TEMP_DIR%\backend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\backend\src" "%TEMP_DIR%\backend\src\" /E /Y /Q >nul

echo [3/5] 复制数据服务源码...
xcopy "%PROJECT_DIR%\data-service\Dockerfile" "%TEMP_DIR%\data-service\" /Y /Q >nul
xcopy "%PROJECT_DIR%\data-service\requirements.txt" "%TEMP_DIR%\data-service\" /Y /Q >nul
xcopy "%PROJECT_DIR%\data-service\app" "%TEMP_DIR%\data-service\app\" /E /Y /Q >nul

echo [4/5] 复制前端源码...
xcopy "%PROJECT_DIR%\frontend\Dockerfile" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\package.json" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\vite.config.js" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\index.html" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\nginx.conf" "%TEMP_DIR%\frontend\" /Y /Q >nul
xcopy "%PROJECT_DIR%\frontend\src" "%TEMP_DIR%\frontend\src\" /E /Y /Q >nul

echo [4/5] 复制 SQL...
xcopy "%PROJECT_DIR%\sql" "%TEMP_DIR%\sql\" /E /Y /Q >nul

echo [5/5] 打包为 tar.gz...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: 使用 tar（Windows 10+ 内置）
tar -czf "%OUTPUT_DIR%\%ARCHIVE_NAME%" -C "%TEMP%" ai-stock-advisor-deploy

:: 清理
rmdir /s /q "%TEMP_DIR%"

echo.
echo ===================================
echo  打包完成！
echo  输出: %OUTPUT_DIR%\%ARCHIVE_NAME%
echo ===================================
echo.
echo 使用方法:
echo   1. 将 %ARCHIVE_NAME% 上传到服务器
echo   2. tar -xzf %ARCHIVE_NAME%
echo   3. cd ai-stock-advisor-deploy
echo   4. vi config.env  (填写 LLM_API_KEY)
echo   5. bash install.sh
echo.
pause
```

- [ ] **步骤 2：Commit**

```bash
git add deploy/pack.bat
git commit -m "feat(deploy): 添加 Windows 打包脚本"
```

---

### 任务 6：验证与文档更新

**文件：**
- 修改：`README.md`（添加部署包使用说明）

- [ ] **步骤 1：在 README.md 的"快速启动"部分后添加生产部署章节**

在现有 README.md 的 `## 配置` 之前添加：

```markdown
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
```

- [ ] **步骤 2：Commit**

```bash
git add README.md
git commit -m "docs: README 添加生产部署说明"
```

---

## 自检结果

**规格覆盖度：** 所有设计规格中的项目均有对应任务：
- ✓ config.env 模板（任务 1）
- ✓ MySQL/Redis 生产配置（任务 1）
- ✓ docker-compose.prod.yml（任务 2）
- ✓ 运维脚本 6 个 + systemd 服务（任务 3）
- ✓ install.sh 7 步流程（任务 4）
- ✓ pack.bat 打包脚本（任务 5）
- ✓ README 更新（任务 6）

**占位符扫描：** 无 TODO、无"待定"、所有代码步骤包含完整实现。

**类型一致性：** 所有路径、变量名、compose service 名称在各任务间保持一致。
