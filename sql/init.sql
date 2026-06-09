CREATE TABLE IF NOT EXISTS policy_news (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(50) NOT NULL COMMENT '来源',
    title VARCHAR(200) NOT NULL COMMENT '标题',
    url VARCHAR(500) NOT NULL COMMENT '原文链接',
    summary TEXT COMMENT '摘要',
    keywords VARCHAR(500) COMMENT '关键词',
    related_sectors VARCHAR(500) COMMENT '关联板块',
    publish_time DATETIME COMMENT '发布时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_url (url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='政策资讯';

CREATE TABLE IF NOT EXISTS stock_recommendation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) NOT NULL COMMENT '股票名称',
    sector VARCHAR(100) COMMENT '所属板块',
    total_score DECIMAL(5,2) COMMENT '综合评分',
    reason TEXT COMMENT '筛选理由',
    rule_scores JSON COMMENT '各规则得分',
    recommend_date DATE NOT NULL COMMENT '推荐日期',
    recommend_price DECIMAL(10,2) COMMENT '推荐时价格',
    buy_price DECIMAL(10,2) COMMENT '建议买入价',
    buy_type VARCHAR(100) COMMENT '买入方式说明',
    take_profit_price DECIMAL(10,2) COMMENT '止盈价',
    stop_loss_price DECIMAL(10,2) COMMENT '止损价',
    support_level DECIMAL(10,2) COMMENT '支撑位',
    resistance_level DECIMAL(10,2) COMMENT '压力位',
    max_hold_days INT DEFAULT 10 COMMENT '最大持有天数',
    sell_price DECIMAL(10,2) COMMENT '实际卖出价',
    sell_type VARCHAR(100) COMMENT '卖出原因',
    sell_date DATE COMMENT '卖出日期',
    profit_pct DECIMAL(5,2) COMMENT '实际收益率(%)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_date (recommend_date),
    INDEX idx_unsold (sell_price, recommend_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日选股';

CREATE TABLE IF NOT EXISTS recommendation_tracking (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    recommendation_id BIGINT NOT NULL,
    days_after INT NOT NULL COMMENT 'T+N',
    close_price DECIMAL(10,2) COMMENT '收盘价',
    change_pct DECIMAL(5,2) COMMENT '涨跌幅(%)',
    tracked_at DATE NOT NULL,
    INDEX idx_rec_id (recommendation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='跟踪记录';

CREATE TABLE IF NOT EXISTS screening_rules (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '规则名称',
    description TEXT COMMENT '规则描述',
    category VARCHAR(50) COMMENT '分类',
    weight DECIMAL(5,2) DEFAULT 1.00 COMMENT '权重',
    win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '胜率(%)',
    total_used INT DEFAULT 0 COMMENT '使用次数',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    source VARCHAR(20) DEFAULT 'preset' COMMENT '来源',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='筛选规则';

CREATE TABLE IF NOT EXISTS chat_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(20) NOT NULL COMMENT '角色',
    content TEXT NOT NULL COMMENT '消息内容',
    context_data JSON COMMENT '上下文数据',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话历史';

-- 预置筛选规则
INSERT INTO screening_rules (name, description, category, weight, status, source) VALUES
('政策利好板块', '最新政策关键词匹配个股所属行业，匹配则加分', '政策', 1.50, 'active', 'preset'),
('MA5上穿MA20', '5日均线上穿20日均线，短期趋势转多', '技术', 1.00, 'active', 'preset'),
('MACD金叉', 'DIF上穿DEA，动能转正', '技术', 1.00, 'active', 'preset'),
('放量突破', '成交量放大至5日均量2倍以上且价格突破前高', '技术', 1.20, 'active', 'preset'),
('PE合理', 'PE低于行业均值，估值偏低', '基本面', 0.80, 'active', 'preset'),
('营收增长', '近一季度营收同比增长>10%', '基本面', 0.80, 'active', 'preset'),
('主力净流入', '当日主力资金净流入为正', '资金', 1.00, 'active', 'preset'),
('北向资金买入', '近3日北向资金累计净买入', '资金', 0.90, 'active', 'preset');


CREATE TABLE IF NOT EXISTS backtest_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    win_rate DECIMAL(5,2) COMMENT '胜率(%)',
    avg_return DECIMAL(5,2) COMMENT '平均收益率(%)',
    total_trades INT COMMENT '总交易数',
    best_weights JSON COMMENT '最优权重',
    best_params JSON COMMENT '最优参数',
    periods_used JSON COMMENT '使用的回测时期',
    applied TINYINT DEFAULT 0 COMMENT '是否已应用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测进化历史';


CREATE TABLE IF NOT EXISTS stock_kline_cache (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open_price DECIMAL(10,2) COMMENT '开盘价',
    close_price DECIMAL(10,2) COMMENT '收盘价',
    high_price DECIMAL(10,2) COMMENT '最高价',
    low_price DECIMAL(10,2) COMMENT '最低价',
    volume BIGINT COMMENT '成交量',
    amount DECIMAL(20,2) COMMENT '成交额',
    UNIQUE KEY uk_code_date (stock_code, trade_date),
    INDEX idx_code (stock_code),
    INDEX idx_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='K线数据缓存';
