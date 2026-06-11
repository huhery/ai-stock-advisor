-- 政策资讯表新增分类和语言字段
-- 用于区分国内政策/国际财经/美联储资讯，以及中文/英文内容
ALTER TABLE policy_news ADD COLUMN category VARCHAR(20) DEFAULT 'domestic' COMMENT '分类: domestic/international/fed';
ALTER TABLE policy_news ADD COLUMN language VARCHAR(10) DEFAULT 'zh' COMMENT '语言: zh/en';
