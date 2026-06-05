#!/bin/bash
# 启动 AI 股票助手所有服务
set -e

INSTALL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$INSTALL_DIR"

echo "正在启动 AI 股票助手..."
docker compose -f docker-compose.prod.yml up -d
echo "启动完成。运行 scripts/status.sh 查看状态。"
