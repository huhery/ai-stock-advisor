"""初始化微淼课程体系的筛选规则

来源：微淼商学院《财务自由操作系统课》第四周 A 股投资方法

核心框架：好公司 + 好价格 + 长期持有
- 好公司：ROE连续5年>15%、净利润现金含量>80%、毛利率>30%
- 好价格：股息率>国债利率、PE<合理估值
- 五项禁令：不投机、不预测趋势、不短期炒作

使用方法：
    python scripts/init_weimu_rules.py --host 81.69.42.239 --password AiStock2026!
"""
import argparse
import pymysql


# 微淼课程体系选股规则
WEIMU_RULES = [
    # ===== 好公司标准 =====
    ('ROE连续优秀', 'ROE连续5年>15%，说明公司盈利能力强且有持续性', '基本面', 2.00),
    ('净利润现金含量高', '净利润现金含量连续5年>80%，说明公司赚的是真金白银不是纸面利润', '基本面', 1.80),
    ('毛利率持续高', '毛利率连续5年>30%，说明产品有定价权，竞争优势明显，安全性高', '基本面', 1.50),
    ('上市满3年', '上市超过3年的公司已度过财报美化期，数据更可信', '基本面', 1.00),
    ('持续分红', '连续3年以上有现金分红，说明是生钱资产而非耗钱资产', '基本面', 1.80),
    ('股息率达标', '股息率>3%（高于银行存款利率），说明买入价格合理，属于正向现金流资产', '价值', 2.00),

    # ===== 好价格标准 =====
    ('PE低于合理估值', 'PE<行业平均PE或历史PE中位数，处于相对低估区间', '价值', 1.50),
    ('PB低于合理值', 'PB<行业平均，资产折价买入更安全', '价值', 1.20),

    # ===== 风控规则（负面筛选）=====
    ('非ST股', '排除ST和*ST股票，远离烂公司和有退市风险的公司', '风控', 1.00),
    ('无大股东频繁减持', '近半年大股东减持次数<2，频繁减持说明内部人不看好', '风控', 1.20),
    ('资产负债率安全', '资产负债率<60%（银行除外），避免高杠杆风险', '风控', 1.30),
    ('净利润正增长', '近一年净利润同比增长>0，避免买入业绩下滑的公司', '基本面', 1.20),
]


def main():
    parser = argparse.ArgumentParser(description='初始化微淼课程选股规则')
    parser.add_argument('--host', default='81.69.42.239')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--user', default='root')
    parser.add_argument('--password', default='AiStock2026!')
    parser.add_argument('--database', default='ai_stock')
    parser.add_argument('--replace', action='store_true', help='清空旧规则后重新插入')
    args = parser.parse_args()

    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, database=args.database, charset='utf8mb4'
    )

    with conn.cursor() as cursor:
        if args.replace:
            cursor.execute("DELETE FROM screening_rules WHERE source = 'preset'")
            print("已清空旧的预置规则")

        sql = """INSERT INTO screening_rules (name, description, category, weight, status, source)
                 VALUES (%s, %s, %s, %s, 'active', 'preset')"""
        count = 0
        for name, desc, cat, weight in WEIMU_RULES:
            # 检查是否已存在
            cursor.execute("SELECT COUNT(*) as cnt FROM screening_rules WHERE name = %s", (name,))
            result = cursor.fetchone()
            existing = result[0] if isinstance(result, tuple) else result.get('cnt', 0)
            if existing > 0:
                print(f"  跳过已存在: {name}")
                continue
            cursor.execute(sql, (name, desc, cat, weight))
            count += 1

    conn.commit()
    conn.close()
    print(f"\n成功插入 {count} 条微淼体系选股规则")
    print("\n规则体系说明：")
    print("  [好公司] ROE>15% + 净利润现金含量>80% + 毛利率>30% + 持续分红")
    print("  [好价格] 股息率>3% + PE低估")
    print("  [风控]   非ST + 低负债 + 无大股东减持 + 利润正增长")


if __name__ == '__main__':
    main()
