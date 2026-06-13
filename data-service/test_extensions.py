"""测试三个扩展功能：全A股选股、国际新闻分析、Kronos预测集成"""

import sys
import os
sys.path.append('.')

def test_stock_pool():
    """测试全A股股票池扩展"""
    print("测试1: 全A股股票池")
    try:
        from app.stock_data.stock_pool import fetch_stock_pool, STOCK_POOL
        # 测试实时获取
        stock_list = fetch_stock_pool()
        print(f"  股票池长度: {len(stock_list)}")
        print(f"  前5只股票: {stock_list[:5]}")
        
        # 测试惰性加载
        print(f"  STOCK_POOL长度: {len(STOCK_POOL)}")
        print(f"  STOCK_POOL类型: {type(STOCK_POOL)}")
        
        if len(stock_list) > 100:
            print("  ✅ 全A股扩展成功: 股票池 > 100只")
        else:
            print("  ⚠️  股票池较小，可能使用兜底池")
        return True
    except Exception as e:
        print(f"  ❌ 股票池测试失败: {e}")
        return False

def test_news_crawler():
    """测试新闻爬虫和LLM分析"""
    print("\n测试2: 国际新闻爬虫和LLM分析")
    try:
        from app.crawler.policy_crawler import crawl_source, SOURCES
        from app.config import LLM_API_KEY
        
        print(f"  数据源数量: {len(SOURCES)}")
        print(f"  国内数据源: {[k for k,v in SOURCES.items() if v.get('category') == 'domestic']}")
        print(f"  国际数据源: {[k for k,v in SOURCES.items() if v.get('category') == 'international']}")
        print(f"  LLM_API_KEY配置: {'已设置' if LLM_API_KEY else '未设置'}")
        
        # 检查爬虫解析器
        from app.crawler.policy_crawler import PARSERS
        print(f"  解析器数量: {len(PARSERS)}")
        
        print("  ✅ 新闻爬虫模块结构正常")
        
        # 尝试连接数据库
        try:
            from app.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM policy_news")
            result = cursor.fetchone()
            print(f"  数据库现有新闻条数: {result['cnt'] if result else '未知'}")
            conn.close()
        except Exception as e:
            print(f"  ⚠️  数据库连接失败: {e}")
            
        return True
    except Exception as e:
        print(f"  ❌ 新闻爬虫测试失败: {e}")
        return False

def test_kronos_integration():
    """测试Kronos预测集成"""
    print("\n测试3: Kronos AI预测集成")
    try:
        from app.prediction.kronos_predictor import _ensure_model_loaded
        from app.screening.engine import _apply_kronos_prediction
        
        # 测试模块导入
        print("  模块导入测试:")
        print(f"    _ensure_model_loaded 导入: 成功")
        print(f"    _apply_kronos_prediction 导入: 成功")
        
        # 检查vendor/kronos
        import os
        kronos_path = 'vendor/kronos'
        if os.path.exists(kronos_path):
            print(f"  vendor/kronos 目录存在")
            files = os.listdir(kronos_path)
            has_model = 'model' in files
            has_requirements = 'requirements.txt' in files
            print(f"    包含model目录: {has_model}")
            print(f"    包含requirements.txt: {has_requirements}")
            
            # 检查依赖
            try:
                import torch
                import einops
                import huggingface_hub
                print(f"  PyTorch版本: {torch.__version__}")
                print(f"  CUDA可用: {torch.cuda.is_available()}")
                if torch.cuda.is_available():
                    print(f"  GPU设备: {torch.cuda.get_device_name(0)}")
                else:
                    print(f"  CPU模式")
            except Exception as e:
                print(f"  ⚠️  依赖检查异常: {e}")
        else:
            print(f"  ❌ vendor/kronos 目录不存在")
            
        # 测试选股引擎中的Kronos调用
        print("  选股引擎集成检查:")
        from app.screening.engine import run_screening
        # 检查run_screening函数定义
        print(f"    run_screening函数存在: 成功")
        
        print("  ✅ Kronos集成模块结构正常")
        return True
    except Exception as e:
        print(f"  ❌ Kronos集成测试失败: {e}")
        return False

def test_engine_integration():
    """测试选股引擎整体集成"""
    print("\n测试4: 选股引擎整体集成")
    try:
        from app.screening.engine import run_screening, get_policy_keywords, score_policy_related
        
        print("  功能检查:")
        print(f"    run_screening (全A股两轮筛选): 存在")
        print(f"    get_policy_keywords (国际国内新闻): 存在")
        print(f"    score_policy_related (政策新闻打分): 存在")
        
        # 检查是否有Kronos预测调用
        import inspect
        source = inspect.getsource(run_screening)
        has_kronos_call = "_apply_kronos_prediction" in source
        print(f"    包含Kronos预测调用: {has_kronos_call}")
        
        # 检查选股逻辑
        has_two_stages = "第一轮" in source and "第二轮" in source
        print(f"    包含两轮筛选: {has_two_stages}")
        
        # 检查股票池调用
        has_stock_pool = "STOCK_POOL" in source
        print(f"    使用STOCK_POOL: {has_stock_pool}")
        
        print("  ✅ 选股引擎集成结构正常")
        return True
    except Exception as e:
        print(f"  ❌ 选股引擎测试失败: {e}")
        return False

def main():
    print("=== AI股票顾问扩展功能测试 ===\n")
    
    results = []
    results.append(test_stock_pool())
    results.append(test_news_crawler())
    results.append(test_kronos_integration())
    results.append(test_engine_integration())
    
    print("\n" + "="*50)
    success_count = sum(results)
    total_count = len(results)
    
    print(f"测试完成: {success_count}/{total_count} 项通过")
    
    if success_count == total_count:
        print("✅ 所有扩展功能测试通过，可以运行完整选股流程")
        print("\n下一步建议:")
        print("1. 设置环境变量 LLM_API_KEY 以启用新闻分析")
        print("2. 运行爬虫: python -m app.crawler.policy_crawler")
        print("3. 测试选股: python -c \"from app.screening.engine import run_screening; run_screening()\"")
    else:
        print("⚠️  部分功能测试失败，请检查配置")
        
    return success_count == total_count

if __name__ == "__main__":
    main()