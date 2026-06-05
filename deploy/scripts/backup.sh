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
