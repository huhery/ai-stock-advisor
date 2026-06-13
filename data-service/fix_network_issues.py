"""修复网络问题：东方财富接口不可用时的替代方案"""

import sys
sys.path.append('.')

def test_alternative_apis():
    """测试替代API以获取股票列表"""
    import requests
    import json
    
    apis = [
        {
            'name': '新浪财经全A股接口',
            'url': 'http://hq.sinajs.cn/list=sh000001,sz399001,sz399006',
            'description': '测试新浪财经基础接口'
        },
        {
            'name': '腾讯财经基础接口',
            'url': 'http://qt.gtimg.cn/q=sh000001,sz399001',
            'description': '测试腾讯财经接口'
        },
        {
            'name': '网易财经股票列表',
            'url': 'http://quotes.money.163.com/service/chddata.html?code=0600000&fields=TCLOSE;HIGH;LOW;TOPEN',
            'description': '测试网易财经接口'
        }
    ]
    
    print("测试替代股票数据接口...")
    for api in apis:
        try:
            response = requests.get(api['url'], timeout=10)
            if response.status_code == 200:
                print(f"  ✅ {api['name']}: 可访问 ({len(response.text)} 字符)")
            else:
                print(f"  ❌ {api['name']}: 状态码 {response.status_code}")
        except Exception as e:
            print(f"  ❌ {api['name']}: 连接失败 - {str(e)[:100]}")
    
    print("\n建议解决方案:")
    print("1. 使用本地缓存的股票列表（当前使用兜底池30只股票）")
    print("2. 配置代理以访问东方财富接口")
    print("3. 使用离线股票列表文件")

def test_fallback_solution():
    """创建更完整的本地股票列表"""
    import os
    
    print("\n创建扩展的本地股票列表...")
    
    # 沪深300主要成分股 + 创业板龙头股
    extended_pool = [
        '600519', '000858', '600036', '601318', '000333',  # 茅台、五粮液、招商、平安、美的
        '600900', '601166', '600276', '000651', '601888',  # 长江电力、兴业银行、恒瑞、格力、中免
        '300750', '002475', '600031', '601012', '600809',  # 宁德、立讯、三一、隆基、山西汾酒
        '000568', '002304', '600585', '601658', '002714',  # 泸州老窖、洋河、海螺、邮储、牧原
        '300059', '002352', '600887', '601669', '000725',  # 东方财富、顺丰、伊利、电建、京东方
        '600690', '601398', '600048', '000001', '600000',  # 海尔、工行、保利、平安银行、浦发
        '601939', '601288', '601328', '600028', '601988',  # 建行、农行、交行、中石化、中行
        '600050', '601628', '601601', '601318', '600030',  # 联通、人寿、太保、平安、中信
        # 创业板权重
        '300059', '300750', '300015', '300124', '300014',  # 东方财富、宁德、爱尔眼科、汇川、亿纬
        '300347', '300142', '300408', '300628', '300454',  # 泰格、沃森、三环、亿联、深信服
        # 深证主板
        '000002', '000063', '000100', '000157', '000333',  # 万科、中兴、TCL、中联重科、美的
        '000425', '000538', '000568', '000651', '000725',  # 徐工、云南白药、泸州老窖、格力、京东方
        # 上证主板
        '600000', '600016', '600028', '600030', '600036',  # 浦发、民生、中石化、中信、招商
        '600048', '600050', '600104', '600111', '600196',  # 保利、联通、上汽、北方稀土、复星
        '600519', '600536', '600570', '600585', '600588',  # 茅台、中软、恒生、海螺、用友
        '600690', '600703', '600745', '600809', '600837',  # 海尔、三安、闻泰科技、山西汾酒、海通
        '600887', '600900', '601012', '601066', '601088',  # 伊利、长江电力、隆基、中信建投、中国神华
        '601111', '601138', '601166', '601169', '601186',  # 国航、工业富联、兴业、北京银行、中铁建
        '601211', '601229', '601288', '601318', '601328',  # 国泰君安、上海银行、农行、平安、交行
        '601336', '601398', '601601', '601628', '601658',  # 新华保险、工行、太保、人寿、邮储
        '601668', '601688', '601727', '601766', '601800',  # 中建、华泰、上海电气、中车、交建
        '601818', '601857', '601881', '601888', '601939',  # 光大、中石油、银河、中免、建行
        '601988', '601989', '601998', '603259', '603288',  # 中行、重工、中信银行、药明康德、海天
        '603501', '603799', '603986', '603993', '688981'   # 韦尔、华友、兆易、洛阳钼业、中芯国际
    ]
    
    # 去重
    extended_pool = list(set(extended_pool))
    print(f"扩展股票池包含 {len(extended_pool)} 只股票")
    print(f"前10只: {extended_pool[:10]}")
    
    # 检查是否包含ST股
    non_st_pool = [code for code in extended_pool if not any(prefix in code for prefix in ['ST', 'ST*', '*ST'])]
    print(f"过滤ST后: {len(non_st_pool)} 只股票")
    
    return extended_pool

def update_stock_pool():
    """更新stock_pool.py中的兜底池"""
    import os
    
    current_path = os.path.join('app', 'stock_data', 'stock_pool.py')
    print(f"\n检查当前文件: {current_path}")
    
    if not os.path.exists(current_path):
        print(f"找不到文件: {current_path}")
        return False
    
    try:
        with open(current_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 生成新的兜底池
        new_pool = test_fallback_solution()
        
        # 寻找FALLBACK_POOL定义
        import re
        pattern = r"FALLBACK_POOL = \[(.*?)\]"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            # 替换为新的兜底池
            new_pool_str = "FALLBACK_POOL = [\n"
            # 每行10个，格式化显示
            for i in range(0, len(new_pool), 10):
                batch = new_pool[i:i+10]
                new_pool_str += "    " + ", ".join(f"'{code}'" for code in batch)
                if i + 10 < len(new_pool):
                    new_pool_str += ",\n"
            new_pool_str += "\n]"
            
            new_content = content[:match.start()] + new_pool_str + content[match.end():]
            
            # 备份原文件
            backup_path = current_path + '.bak'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"已备份原文件至: {backup_path}")
            
            # 写入新文件
            with open(current_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ 成功更新股票兜底池至 {len(new_pool)} 只股票")
            
            # 测试新配置
            print("\n测试新配置...")
            from app.stock_data.stock_pool import FALLBACK_POOL
            print(f"新兜底池长度: {len(FALLBACK_POOL)}")
            print(f"示例: {FALLBACK_POOL[:5]}...")
            
            return True
        else:
            print("❌ 在文件中找不到FALLBACK_POOL定义")
            return False
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

def main():
    print("=== 网络问题修复方案 ===\n")
    
    # 测试现有API
    test_alternative_apis()
    
    # 询问用户是否更新兜底池
    print("\n--- 选项 ---")
    print("1. 使��当前的兜底池（30只股票）")
    print("2. 扩展兜底池到 ~100只核心股票")
    
    choice = input("\n请选择（1或2）: ").strip()
    
    if choice == '2':
        success = update_stock_pool()
        if success:
            print("\n✅ 兜底池已扩展，现在包含约100只核心A股")
            print("选股流程将使用这些股票，即使东方财富接口无法访问")
        else:
            print("\n❌ 更新失败，保持原配置")
    else:
        print("\n保持当前配置不变")
    
    print("\n--- 最终建议 ---")
    print("1. 设置环境变量 LLM_API_KEY（用于新闻分析）")
    print("2. 运行爬虫收集新闻: python -m app.crawler.policy_crawler")
    print("3. 测试完整选股流程: python -c \"from app.screening.engine import run_screening; run_screening()\"")
    print("4. 如果东方财富接口仍不可用，建议：")
    print("   a. 检查网络代理设置")
    print("   b. 使用其他数据源（如AkShare、Tushare等）")
    print("   c. 使用本地CSV股票列表文件")

if __name__ == "__main__":
    main()