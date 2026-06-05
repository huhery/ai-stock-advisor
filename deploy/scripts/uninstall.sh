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
