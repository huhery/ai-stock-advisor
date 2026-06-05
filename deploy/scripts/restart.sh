#!/bin/bash
# 重启 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在重启 AI 股票助手..."
docker compose -f docker-compose.prod.yml restart
echo "重启完成。"
