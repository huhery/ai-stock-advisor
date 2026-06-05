#!/bin/bash
# 停止 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在停止 AI 股票助手..."
docker compose -f docker-compose.prod.yml down
echo "已停止。"
