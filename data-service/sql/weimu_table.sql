-- 微淼财务自由选股结果表
-- 如果表已存在但缺少字段，执行 ALTER 语句补充

CREATE TABLE IF NOT EXISTS weimu_recommendation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) DEFAULT NULL COMMENT '股票名称',
    sector VARCHAR(50) DEFAULT NULL COMMENT '所属行业板块',
    recommend_date DATE NOT NULL COMMENT '筛选日期',
    -- 财务指标
    roe_avg DECIMAL(8,2) DEFAULT NULL COMMENT 'ROE均值(%)',
    gross_margin_avg DECIMAL(8,2) DEFAULT NULL COMMENT '毛利率均值(%)',
    cash_ratio_avg DECIMAL(8,2) DEFAULT NULL COMMENT '净利润现金含量均值(%)',
    debt_ratio DECIMAL(8,2) DEFAULT NULL COMMENT '资产负债率(%)',
    dividend_yield DECIMAL(8,2) DEFAULT NULL COMMENT '动态股息率(%)',
    continuous_dividend_years INT DEFAULT 0 COMMENT '连续分红年数',
    -- 估值
    pe DECIMAL(10,2) DEFAULT NULL COMMENT '个股TTM市盈率',
    market_pe DECIMAL(8,2) DEFAULT NULL COMMENT '深证A股整体市盈率',
    -- 结果
    score INT DEFAULT 0 COMMENT '综合评分(0-100)',
    valuation VARCHAR(10) DEFAULT 'wait' COMMENT '估值状态: buy/hold/sell/wait',
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 索引
    INDEX idx_date (recommend_date),
    INDEX idx_code_date (stock_code, recommend_date),
    INDEX idx_valuation (valuation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='微淼财务自由选股结果';

-- ============================================================
-- 兼容旧表：如果表早于 stock_name 字段创建，需手动补列。
-- MySQL 不支持 ADD COLUMN IF NOT EXISTS（8.0 之前），
-- 若列已存在执行会报错(可忽略)，或先用下面的查询判断：
--   SHOW COLUMNS FROM weimu_recommendation LIKE 'stock_name';
-- 不存在时再执行：
-- ALTER TABLE weimu_recommendation
--     ADD COLUMN stock_name VARCHAR(50) DEFAULT NULL COMMENT '股票名称' AFTER stock_code;
