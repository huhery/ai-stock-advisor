"""资产配置建议模块

基于微淼课程的"3-3-1工具"体系和当前市场估值，给出个性化资产配置建议。

核心理念：
- 三大核心工具：股票、REITs、房地产
- 三个辅助工具：国债逆回购、货币基金、债券
- 一个保障工具：保障型保险
- 根据市场PE动态调整各工具的配比

关键原则：
- PE < 20 时加大股票配置（好价格买入）
- PE 20-40 时保持均衡，闲置资金做逆回购/货币基金
- PE > 40 时减少股票，增加防御性配置
- 始终保留 6 个月生活费作为应急资金
"""
from app.weimu.valuation import get_market_pe, get_bond_yield, analyze_market_pe


def generate_allocation_advice(total_capital, monthly_expense=5000):
    """根据资金总额和当前市场环境生成资产配置建议

    Args:
        total_capital: 总投资资金（元）
        monthly_expense: 月生活支出（元），用于计算应急资金

    Returns:
        dict: 完整的资产配置建议
    """
    market_pe = get_market_pe()
    bond_yield = get_bond_yield()
    market_analysis = analyze_market_pe(market_pe)

    # 应急资金 = 6个月生活费（不参与投资）
    emergency_fund = monthly_expense * 6
    # 保险预算 = 年收入的5%左右（这里用总资金的2%作为年度保费预算参考）
    insurance_budget = total_capital * 0.02

    # 可投资资金 = 总资金 - 应急资金
    investable = max(total_capital - emergency_fund, 0)

    # 根据市场PE动态调整配置比例
    allocation = _calculate_allocation(investable, market_pe, bond_yield)

    # 具体投资工具建议
    tools = _generate_tool_suggestions(allocation, market_pe, bond_yield)

    # 操作步骤建议
    steps = _generate_action_steps(allocation, market_pe, total_capital)

    return {
        'total_capital': total_capital,
        'monthly_expense': monthly_expense,
        'emergency_fund': emergency_fund,
        'insurance_budget': round(insurance_budget, 0),
        'investable_capital': round(investable, 0),
        'market_pe': market_pe,
        'bond_yield': bond_yield,
        'market_level': market_analysis['level'],
        'market_advice': market_analysis['advice'],
        'allocation': allocation,
        'tools': tools,
        'steps': steps,
    }


def _calculate_allocation(investable, market_pe, bond_yield):
    """根据市场PE计算各类资产配置比例

    策略逻辑（来自微淼课程思想）：
    - 市场低估时（PE<20）：重仓股票+REITs，少量现金管理
    - 市场合理时（PE 20-40）：均衡配置，大量资金做逆回购等待
    - 市场高估时（PE>40）：极少股票，主要防御

    Returns:
        list: 各资产类别的配置详情
    """
    if market_pe < 15:
        # 极度低估：激进买入
        ratios = {
            'stock': 0.60,       # A股好公司
            'reits': 0.15,       # 港股/美股REITs
            'bond_reverse': 0.10, # 逆回购（短期灵活）
            'money_fund': 0.10,  # 货币基金
            'bond': 0.05,        # 债券
        }
    elif market_pe < 20:
        # 低估：积极配置
        ratios = {
            'stock': 0.50,
            'reits': 0.15,
            'bond_reverse': 0.15,
            'money_fund': 0.10,
            'bond': 0.10,
        }
    elif market_pe < 30:
        # 合理偏低：均衡等待
        ratios = {
            'stock': 0.30,
            'reits': 0.15,
            'bond_reverse': 0.25,
            'money_fund': 0.20,
            'bond': 0.10,
        }
    elif market_pe < 40:
        # 合理：等待为主
        ratios = {
            'stock': 0.15,
            'reits': 0.10,
            'bond_reverse': 0.30,
            'money_fund': 0.30,
            'bond': 0.15,
        }
    elif market_pe < 55:
        # 偏高：防御为主
        ratios = {
            'stock': 0.05,
            'reits': 0.05,
            'bond_reverse': 0.35,
            'money_fund': 0.35,
            'bond': 0.20,
        }
    else:
        # 严重高估：全面防御
        ratios = {
            'stock': 0.00,
            'reits': 0.00,
            'bond_reverse': 0.40,
            'money_fund': 0.40,
            'bond': 0.20,
        }

    allocation = []
    for category, ratio in ratios.items():
        amount = round(investable * ratio, 0)
        allocation.append({
            'category': category,
            'name': _category_name(category),
            'ratio': round(ratio * 100, 1),
            'amount': amount,
            'type': _category_type(category),
        })

    return allocation


def _category_name(category):
    """资产类别中文名"""
    names = {
        'stock': 'A股好公司',
        'reits': 'REITs（房地产信托）',
        'bond_reverse': '国债逆回购',
        'money_fund': '货币基金',
        'bond': '债券/债券基金',
    }
    return names.get(category, category)


def _category_type(category):
    """资产类别类型标签"""
    types = {
        'stock': 'core',         # 核心工具
        'reits': 'core',         # 核心工具
        'bond_reverse': 'cash',  # 现金管理
        'money_fund': 'cash',    # 现金管理
        'bond': 'defense',       # 防御工具
    }
    return types.get(category, 'other')


def _generate_tool_suggestions(allocation, market_pe, bond_yield):
    """为每个类别生成具体的投资工具建议"""
    tools = []

    for item in allocation:
        if item['amount'] <= 0:
            continue

        category = item['category']
        if category == 'stock':
            tools.append({
                'category': 'stock',
                'name': 'A股好公司',
                'amount': item['amount'],
                'suggestions': [
                    '通过本系统"财务自由选股"筛选出的好公司（精选结果）',
                    '分散到 3-5 只目标股，每只均匀配置',
                    '分三批买入：首次1/3，每跌5-10%加仓1/3',
                    f'买入条件：个股PE<15 且 股息率>{bond_yield}%（当前国债收益率）',
                    '2024新规参考：优先选择连续3年分红且分红率>30%的公司（国九条导向）',
                    '红利ETF替代：中证红利ETF(515080)可作为"一篮子好公司"的懒人方案',
                ],
                'risk': '中高',
                'expected_return': '股息4-8% + 价格增值',
                'holding_period': '3-10年长期持有',
            })

        elif category == 'reits':
            tools.append({
                'category': 'reits',
                'name': 'REITs（房地产信托）',
                'amount': item['amount'],
                'suggestions': [
                    '香港REITs：领展(0823)、冠君产业(2778)、越秀房产(0405)',
                    '公募REITs（C-REITs）：中金普洛斯REIT(508056)、华安张江光大REIT(508027)',
                    '中证REITs指数基金：跟踪国内公募REITs的指数产品',
                    '关注分派率 > 5% 的REITs，优先选择底层资产为产业园/仓储/高速公路',
                    '注意：2024年后国内公募REITs已扩容，可直接通过A股账户买入',
                ],
                'risk': '中',
                'expected_return': '分派率4-8%',
                'holding_period': '3-5年',
            })

        elif category == 'bond_reverse':
            tools.append({
                'category': 'bond_reverse',
                'name': '国债逆回购',
                'amount': item['amount'],
                'suggestions': [
                    '上交所：204001(1天)、204003(3天)、204007(7天)',
                    '深交所：131810(1天)、131800(3天)、131801(7天)',
                    '月末/季末/年末时利率较高，可达10-20%年化',
                    '平时年化约2-4%，高于活期存款',
                    '闲置1个月以内的资金首选逆回购',
                ],
                'risk': '无风险',
                'expected_return': f'年化2-4%（特殊时点可达20%）',
                'holding_period': '1-28天灵活',
            })

        elif category == 'money_fund':
            tools.append({
                'category': 'money_fund',
                'name': '货币基金',
                'amount': item['amount'],
                'suggestions': [
                    '余额宝/微信零钱通（灵活取用）',
                    '券商保证金理财（如果资金在证券账户）',
                    '银行T+0理财产品',
                    '闲置1个月以上的资金适合货币基金',
                ],
                'risk': '极低',
                'expected_return': '年化1.5-2.5%',
                'holding_period': '随时可取',
            })

        elif category == 'bond':
            tools.append({
                'category': 'bond',
                'name': '债券/债券基金',
                'amount': item['amount'],
                'suggestions': [
                    '国债：安全性最高，可通过银行或交易所购买',
                    '短债基金：如南方短债、博时短债（年化2-4%）',
                    '中长期纯债基金：市场高估时收益更佳（年化3-5%）',
                    '可转债（转股溢价率<20%时）：兼具债性和股性，下有保底上不封顶',
                    '同业存单指数基金：如华宝添益(511990)，风险极低，优于活期',
                ],
                'risk': '低',
                'expected_return': f'年化3-5%',
                'holding_period': '半年至3年',
            })

    return tools


def _generate_action_steps(allocation, market_pe, total_capital):
    """生成具体操作步骤"""
    steps = []

    # 第一步：永远先确保保障
    steps.append({
        'order': 1,
        'title': '配置保障型保险',
        'description': '先保障后投资。购买定期寿险+重疾险+意外险，年缴保费控制在总资金的1-2%',
        'action': f'年度保费预算约 {int(total_capital * 0.015)} 元',
        'priority': 'high',
    })

    # 第二步：应急资金
    steps.append({
        'order': 2,
        'title': '预留应急资金',
        'description': '6个月生活费存在随时可取的账户，不参与任何投资',
        'action': '存入货币基金或银行活期',
        'priority': 'high',
    })

    # 第三步：根据市场状态决定配置节奏
    if market_pe < 20:
        steps.append({
            'order': 3,
            'title': '当前是买入好时机 — 积极配置股票',
            'description': (
                f'市场PE={market_pe}，处于低估区间。'
                '从财务自由选股结果中选 3-5 只好公司，分三批买入。'
                '第一批投入股票配置金额的1/3，之后每跌5-10%加仓1/3。'
            ),
            'action': '开始执行"运行筛选"，从结果中选择评分最高的好公司',
            'priority': 'high',
        })
    elif market_pe < 30:
        steps.append({
            'order': 3,
            'title': '市场估值合理 — 等待为主，少量配置',
            'description': (
                f'市场PE={market_pe}，处于合理偏低区间。'
                '不急于大量买入股票，可以小仓位买入PE特别低（<12）的好公司。'
                '大部分资金做逆回购和货币基金，耐心等待更好的价格。'
            ),
            'action': '资金先放入逆回购/货币基金，关注好公司等待好价格',
            'priority': 'medium',
        })
    else:
        steps.append({
            'order': 3,
            'title': '市场估值偏高 — 防御为主',
            'description': (
                f'市场PE={market_pe}，不适合买入股票。'
                '将大部分资金配置在逆回购、货币基金和债券中。'
                '耐心等待市场回调，好价格终会出现。'
            ),
            'action': '暂不买入股票，资金全部做现金管理（逆回购+货基）',
            'priority': 'low',
        })

    # 第四步：REITs配置
    steps.append({
        'order': 4,
        'title': '配置REITs获取稳定租金收入',
        'description': (
            'REITs是实现财务自由的核心工具之一。'
            '选择优质物业的REITs，股息率>5%，长期持有收租。'
            '通过港股通可以买入香港上市的REITs。'
        ),
        'action': '开通港股通，关注汇贤产业(87001)、领展(0823)等',
        'priority': 'medium',
    })

    # 第五步：持续学习
    steps.append({
        'order': 5,
        'title': '持续学习 + 制定财务自由计划',
        'description': (
            '投资是终身的事。持续学习财报分析、企业研究。'
            '制定明确的财务自由计划：目标金额、实现时间、执行路径。'
            '记住：不预测，只计算！'
        ),
        'action': '每年阅读持股公司年报，跟踪财务指标变化',
        'priority': 'medium',
    })

    return steps
