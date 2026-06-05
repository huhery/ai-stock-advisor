#!/bin/bash
# 检查 AI 股票助手服务状态

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

# 读取配置
if [ -f .env ]; then
    source .env
fi

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
