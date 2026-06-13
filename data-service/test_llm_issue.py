"""测试为什么没有LLM_API_KEY也能运行"""

import sys
sys.path.append('.')

def analyze_reason():
    print("=" * 60)
    print("分析：为什么没有LLM_API_KEY也能运行")
    print("=" * 60)
    
    # 1. 检查LLM_API_KEY
    from app.config import LLM_API_KEY
    print(f"\n1. LLM_API_KEY检查:")
    print(f"   LLM_API_KEY值: {LLM_API_KEY}")
    print(f"   是否为空: {not bool(LLM_API_KEY)}")
    print(f"   长度: {len(LLM_API_KEY) if LLM_API_KEY else 0}")
    
    # 2. 查看新闻爬虫逻辑
    from app.crawler.policy_crawler import crawl_all_sources
    import inspect
    
    print(f"\n2. 新闻爬虫逻辑分析:")
    source_code = inspect.getsource(crawl_all_sources)
    lines = source_code.split('\n')
    
    # 查找关键行
    print("   爬虫函数关键部分:")
    for i, line in enumerate(lines):
        if 'new_items' in line and 'analyze_news_impact' in line:
            print(f"     第{i+1}行: {line.strip()}")
        if 'print(' in line and '新增' in line:
            print(f"     第{i+1}行: {line.strip()}")
    
    # 3. 模拟爬虫场景
    print(f"\n3. 模拟不同场景:")
    
    print("   场景A: 有新新闻 (new_items不为空)")
    from app.crawler.policy_crawler import analyze_news_impact
    
    mock_news = [{'title': '测试新闻', 'source': '测试源'}]
    print(f"   调用 analyze_news_impact(mock_news)...")
    try:
        analyze_news_impact(mock_news)
        print("   ✅ 调用完成")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    print(f"\n   场景B: 没有新新闻 (new_items为空)")
    print(f"   调用 analyze_news_impact([])...")
    try:
        analyze_news_impact([])
        print("   ✅ 调用完成")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    # 4. 查看数据库中的新闻
    print(f"\n4. 数据库状态检查:")
    from app.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否有新闻
            cursor.execute("SELECT COUNT(*) as cnt FROM policy_news")
            result = cursor.fetchone()
            total_news = result['cnt'] if result else 0
            print(f"   总新闻数: {total_news}")
            
            # 检查是否有keywords
            cursor.execute("SELECT COUNT(*) as cnt FROM policy_news WHERE keywords IS NOT NULL")
            result = cursor.fetchone()
            news_with_keywords = result['cnt'] if result else 0
            print(f"   已分析关键词的新闻: {news_with_keywords}")
            
            # 检查新增新闻
            cursor.execute("SELECT MAX(created_at) as latest FROM policy_news")
            result = cursor.fetchone()
            latest = result['latest'].strftime('%Y-%m-%d %H:%M:%S') if result and result['latest'] else '未知'
            print(f"   最新新闻时间: {latest}")
    finally:
        conn.close()

def check_system_flow():
    print(f"\n" + "=" * 60)
    print("系统运行流程解析")
    print("=" * 60)
    
    print("\n从你的日志分析:")
    print("时间线:")
    print("  00:41:46 - Kronos加载模型")
    print("  00:42:01 - Kronos模型加载完成")
    print("  00:42:07 - 选股完成，推荐10只股票")
    print("  00:42:37 - 开始爬取新闻")
    print("  00:43:22 - 爬取完成，共26条资讯，新增0条")
    
    print(f"\n关键发现:")
    print("  1. Kronos和选股功能独立运行 ✅")
    print("  2. 新闻爬虫运行了（国内源成功，国际源失败）")
    print("  3. '新增0条' - 没有新新闻，因此没有调用LLM分析")
    print("  4. 没有看到'[跳过] 未配置LLM_API_KEY'消息，因为没调用analyze_news_impact")
    
    print(f"\n代码流程:")
    print("  crawl_all_sources() → 爬取新闻")
    print("  ↓")
    print("  有new_items? → 是 → analyze_news_impact(new_items)")
    print("  ↓")
    print("  LLM_API_KEY检查 → 无 → 打印'[跳过]'消息")
    print("  ↓")
    print("  但实际：new_items为空 → 直接跳过 → 不打印消息")

def explain_why_no_error():
    print(f"\n" + "=" * 60)
    print("为什么没有报错？")
    print("=" * 60)
    
    print("\n正确理解:")
    print("  1. 系统没有'报错'，而是'跳过'了LLM分析")
    print("  2. 但跳过的逻辑没有被触发，因为根本没有新新闻")
    print("  3. 核心功能（选股、Kronos预测）不依赖LLM_API_KEY")
    
    print(f"\n打个比方:")
    print("  就像一个餐厅:")
    print("  - 主厨（选股引擎）正常工作")
    print("  - 助手（Kronos预测）正常工作")
    print("  - 采购员（新闻爬虫）去市场，但没买到新食材")
    print("  - 因为没有新食材，所以不需要叫外卖（LLM分析）")
    print("  - 餐厅正常营业，客人不会知道外卖服务没用到")

def what_happens_with_llm_key():
    print(f"\n" + "=" * 60)
    print("如果设置了LLM_API_KEY会怎样？")
    print("=" * 60)
    
    print("\n变化:")
    print("  1. 当有新新闻时，会调用LLM分析")
    print("  2. LLM会分析新闻对A股板块的影响")
    print("  3. 提取关键词和受益板块存入数据库")
    print("  4. 选股时会根据关键词给相关股票加分")
    
    print(f"\n增强效果:")
    print("  - 股票推荐会更贴合新闻热点")
    print("  - 比如'新能源'政策利好 → 新能源板块股票加分")
    print("  - '降息'新闻 → 银行、地产股加分")
    print("  - '芯片'技术突破 → 半导体股票加分")

def main():
    analyze_reason()
    check_system_flow()
    explain_why_no_error()
    what_happens_with_llm_key()
    
    print(f"\n" + "=" * 60)
    print("结论")
    print("=" * 60)
    print("\n✅ 系统设计是合理的:")
    print("  1. 即使没有LLM_API_KEY，核心功能也能运行")
    print("  2. LLM分析是可选的增强功能")
    print("  3. 没有新新闻时，不会尝试调用LLM")
    print("  4. 有LLM_API_KEY时，新闻分析能提升选股质量")
    
    print(f"\n🔍 验证方法:")
    print("  1. 清空数据库的新闻: DELETE FROM policy_news")
    print("  2. 运行爬虫: python -m app.crawler.policy_crawler")
    print("  3. 查看是否会打印'[跳过] 未配置LLM_API_KEY'")
    
    print(f"\n💡 建议:")
    print("  如果你需要新闻分析功能:")
    print("  1. 获取DeepSeek API密钥")
    print("  2. 设置环境变量: set LLM_API_KEY=你的密钥")
    print("  3. 清空新闻表后重新爬取")
    print("  4. 观察LLM分析效果")

if __name__ == "__main__":
    main()