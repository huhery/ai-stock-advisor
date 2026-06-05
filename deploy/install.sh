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
