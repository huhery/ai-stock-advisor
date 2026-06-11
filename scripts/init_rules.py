"""初始化筛选规则到数据库

使用方法：
    python scripts/init_rules.py --host 81.69.42.239 --password AiStock2026!
"""
import argparse
import pymysql


RULES = [
    ('政策利好板块', '最新政策关键词匹配个股所属行业，匹配则加分', '政策', 1.50),
    ('MA5上穿MA20', '5日均线上穿20日均线，短期趋势转多', '技术', 1.00),
    ('MACD金叉', 'DIF上穿DEA，动能转正', '技术', 1.00),
    ('放量突破', '成交量放大至5日均量2倍以上且价格突破前高', '技术', 1.20),
    ('PE合理', 'PE低于行业均值，估值偏低', '基本面', 0.80),
    ('营收增长', '近一季度营收同比增长>10%', '基本面', 0.80),
    ('主力净流入', '当日主力资金净流入为正', '资金', 1.00),
    ('北向资金买入', '近3日北向资金累计净买入', '资金', 0.90),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='81.69.42.239')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', default='AiStock2026!')
    parser.add_argument('--database', default='ai_stock')
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, database=args.database, charset='utf8mb4'
    )

    with conn.cursor() as cursor:
        # 确保表存在
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screening_rules (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                weight DECIMAL(5,2) DEFAULT 1.00,
                win_rate DECIMAL(5,2) DEFAULT 0.00,
                total_used INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'active',
                source VARCHAR(20) DEFAULT 'preset',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 检查是否已有数据
        cursor.execute("SELECT COUNT(*) as cnt FROM screening_rules")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"已有 {count} 条规则，跳过初始化")
            conn.close()
            return

        # 插入规则
        sql = """INSERT INTO screening_rules (name, description, category, weight, status, source)
                 VALUES (%s, %s, %s, %s, 'active', 'preset')"""
        for name, desc, cat, weight in RULES:
            cursor.execute(sql, (name, desc, cat, weight))

    conn.commit()
    conn.close()
    print(f"成功插入 {len(RULES)} 条筛选规则")


if __name__ == '__main__':
    main()
