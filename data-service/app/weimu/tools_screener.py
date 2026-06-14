"""投资工具筛选模块

从公开接口实时获取各类投资工具数据，给出具体买哪个的推荐：
1. REITs（公募C-REITs + 港股REITs）
2. 货币基金（7日年化收益率排行）
3. 债券基金（短债/中长债/可转债基金）
4. 国债逆回购（实时利率）

数据源：天天基金网(fund.eastmoney.com) + 东方财富行情接口
"""
import time
import json
import re

try:
    from curl_cffi import requests as http
    IMPERSONATE = True
except ImportError:
    import requests as http
    IMPERSONATE = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
}


def get_all_tools_recommendations():
    """获取所有投资工具的推荐结果

    Returns:
        dict: 包含各类工具的推荐列表
    """
    results = {
        'reits': get_reits_recommendations(),
        'money_fund': get_money_fund_recommendations(),
        'bond_fund': get_bond_fund_recommendations(),
        'reverse_repo': get_reverse_repo_info(),
    }
    return results


# ===== 1. 公募REITs筛选 =====

def get_reits_recommendations():
    """获取公募C-REITs推荐

    从东方财富获取A股上市的公募REITs，按分派率排序。
    """
    reits = []

    # 公募REITs列表（沪深交易所）
    try:
        # 东方财富REITs专区接口
        url = (
            "http://82.push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=50&po=1&np=1"
            "&ut=bd1d9ddb04089700cf9c27f6f7426281"
            "&fltt=2&invt=2&fid=f3"
            "&fs=m:1+t:26,m:0+t:29"  # REITs板块
            "&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            items = data.get('data', {}).get('diff', [])
            for item in items:
                code = item.get('f12', '')
                name = item.get('f14', '')
                price = item.get('f2')
                change_pct = item.get('f3')
                if code and name and price:
                    reits.append({
                        'code': code,
                        'name': name,
                        'price': round(float(price) / 100, 3) if price else None,
                        'change_pct': round(float(change_pct) / 100, 2) if change_pct else None,
                        'type': 'C-REITs',
                        'market': 'A股',
                    })
    except Exception as e:
        print(f"  [REITs] 东方财富接口失败: {e}")

    # 如果接口获取失败，使用预设的优质REITs清单
    if not reits:
        reits = _get_preset_reits()

    return {
        'title': 'REITs（公募基础设施REITs）',
        'description': '公募REITs是实现财务自由的核心工具之一，通过持有优质基础设施获取稳定分红',
        'items': reits[:15],
        'buy_criteria': '分派率>5%，底层资产为产业园/仓储/高速公路/数据中心优先',
        'risk': '中',
    }


def _get_preset_reits():
    """预设的优质公募REITs清单"""
    return [
        {'code': '508056', 'name': '中金普洛斯REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '仓储物流'},
        {'code': '508027', 'name': '华安张江光大REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '产业园'},
        {'code': '508000', 'name': '华安张江REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '产业园'},
        {'code': '508001', 'name': '沪杭甬REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '高速公路'},
        {'code': '508018', 'name': '中金安徽交控REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '高速公路'},
        {'code': '508009', 'name': '建信中关村REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '产业园'},
        {'code': '508006', 'name': '国金铁建重庆REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '高速公路'},
        {'code': '180201', 'name': '中金厦门安居REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '保障性租赁住房'},
        {'code': '508058', 'name': '中信建投国家电投REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '新能源'},
        {'code': '508099', 'name': '建信中联REIT', 'type': 'C-REITs', 'market': 'A股', 'category': '数据中心'},
    ]


# ===== 2. 货币基金筛选 =====

def get_money_fund_recommendations():
    """获取货币基金推荐（按7日年化收益率排行）

    数据源：天天基金网基金排行接口
    """
    funds = []

    try:
        # 天天基金 货币基金排行接口
        url = (
            "http://fund.eastmoney.com/data/rankhandler.aspx"
            "?op=ph&dt=kf&ft=hb&rs=&gs=0&sc=1nzf&st=desc"
            "&pi=1&pn=20&dx=1"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            # 天天基金返回的是JS变量格式，需要解析
            text = resp.text
            # 提取 datas 数组
            match = re.search(r'datas:(.*?),allRecords', text, re.DOTALL)
            if match:
                data_str = match.group(1).strip()
                items = json.loads(data_str)
                for item in items:
                    parts = item.split(',')
                    if len(parts) >= 10:
                        funds.append({
                            'code': parts[0],
                            'name': parts[1],
                            'yield_7d': parts[4] if parts[4] else None,  # 7日年化
                            'yield_10k': parts[3] if parts[3] else None,  # 万份收益
                            'type': '货币基金',
                        })
    except Exception as e:
        print(f"  [货币基金] 天天基金接口失败: {e}")

    # 兜底
    if not funds:
        funds = _get_preset_money_funds()

    return {
        'title': '货币基金',
        'description': '闲置资金的最佳去处，随时可取，年化1-2%，优于银行活期',
        'items': funds[:10],
        'buy_criteria': '选规模>100亿的大型货基，7日年化收益率排名靠前',
        'risk': '极低',
    }


def _get_preset_money_funds():
    """预设货币基金推荐"""
    return [
        {'code': '000198', 'name': '天治天得利货币', 'type': '货币基金', 'note': '券商可买'},
        {'code': '003003', 'name': '华夏现金增利A', 'type': '货币基金', 'note': '规模大'},
        {'code': '000509', 'name': '万家日日薪货币A', 'type': '货币基金', 'note': '收益率较高'},
        {'code': '511990', 'name': '华宝添益(场内)', 'type': '货币基金', 'note': '场内交易，T+0'},
        {'code': '511880', 'name': '银华日利(场内)', 'type': '货币基金', 'note': '场内交易，T+0'},
        {'code': '000343', 'name': '鹏华增值宝货币', 'type': '货币基金', 'note': ''},
        {'code': '004137', 'name': '博时合惠货币B', 'type': '货币基金', 'note': ''},
        {'code': '000638', 'name': '富国富钱包货币', 'type': '货币基金', 'note': ''},
    ]


# ===== 3. 债券基金筛选 =====

def get_bond_fund_recommendations():
    """获取债券基金推荐

    分三类：短债基金、中长期纯债、可转债基金
    """
    short_bond = []
    long_bond = []
    convertible = []

    try:
        # 短期纯债基金排行
        url = (
            "http://fund.eastmoney.com/data/rankhandler.aspx"
            "?op=ph&dt=kf&ft=dq&rs=&gs=0&sc=1nzf&st=desc"
            "&pi=1&pn=15&dx=1"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            text = resp.text
            match = re.search(r'datas:(.*?),allRecords', text, re.DOTALL)
            if match:
                items = json.loads(match.group(1).strip())
                for item in items[:10]:
                    parts = item.split(',')
                    if len(parts) >= 8:
                        short_bond.append({
                            'code': parts[0],
                            'name': parts[1],
                            'yield_1y': parts[5] if len(parts) > 5 and parts[5] else None,
                            'type': '短债基金',
                        })
    except Exception as e:
        print(f"  [债券基金] 短债排行获取失败: {e}")

    try:
        # 中长期纯债基金排行
        url = (
            "http://fund.eastmoney.com/data/rankhandler.aspx"
            "?op=ph&dt=kf&ft=zq&rs=&gs=0&sc=1nzf&st=desc"
            "&pi=1&pn=15&dx=1"
        )
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            text = resp.text
            match = re.search(r'datas:(.*?),allRecords', text, re.DOTALL)
            if match:
                items = json.loads(match.group(1).strip())
                for item in items[:10]:
                    parts = item.split(',')
                    if len(parts) >= 8:
                        long_bond.append({
                            'code': parts[0],
                            'name': parts[1],
                            'yield_1y': parts[5] if len(parts) > 5 and parts[5] else None,
                            'type': '债券基金',
                        })
    except Exception as e:
        print(f"  [债券基金] 中长债排行获取失败: {e}")

    # 兜底
    if not short_bond:
        short_bond = [
            {'code': '006965', 'name': '南方短债A', 'type': '短债基金', 'note': '规模大稳定'},
            {'code': '006517', 'name': '博时短债A', 'type': '短债基金', 'note': ''},
            {'code': '003033', 'name': '嘉实超短债A', 'type': '短债基金', 'note': ''},
            {'code': '006647', 'name': '广发短债A', 'type': '短债基金', 'note': ''},
            {'code': '007147', 'name': '中欧短债A', 'type': '短债基金', 'note': ''},
        ]

    if not long_bond:
        long_bond = [
            {'code': '050003', 'name': '博时现金收益A', 'type': '债券基金', 'note': ''},
            {'code': '000087', 'name': '嘉实中短债A', 'type': '债券基金', 'note': ''},
            {'code': '519519', 'name': '华安安心收益A', 'type': '债券基金', 'note': ''},
            {'code': '110027', 'name': '易方达安心回报A', 'type': '债券基金', 'note': ''},
            {'code': '070020', 'name': '嘉实稳固收益A', 'type': '债券基金', 'note': ''},
        ]

    all_bonds = short_bond + long_bond
    return {
        'title': '债券基金',
        'description': '比货币基金收益高，风险仍然较低，适合中期闲置资金',
        'items': all_bonds[:15],
        'buy_criteria': '优先选短债基金（波动小），规模>10亿，近1年收益>3%',
        'risk': '低',
        'sub_categories': {
            'short_bond': {'title': '短债基金（推荐）', 'items': short_bond[:5]},
            'long_bond': {'title': '中长期纯债', 'items': long_bond[:5]},
        }
    }


# ===== 4. 国债逆回购信息 =====

def get_reverse_repo_info():
    """获取国债逆回购实时利率

    数据源：腾讯行情接口（上交所逆回购品种）
    """
    repos = []
    # 上交所逆回购品种代码
    repo_codes = {
        '204001': '1天期',
        '204002': '2天期',
        '204003': '3天期',
        '204004': '4天期',
        '204007': '7天期',
        '204014': '14天期',
        '204028': '28天期',
        '204091': '91天期',
        '204182': '182天期',
    }

    try:
        codes_str = ','.join([f'sh{c}' for c in repo_codes.keys()])
        url = f"http://qt.gtimg.cn/q={codes_str}"
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=10, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=10)

        resp.encoding = 'gbk'
        for line in resp.text.strip().split('\n'):
            if '~' not in line:
                continue
            parts = line.split('~')
            if len(parts) < 5:
                continue
            code = parts[2]
            price = parts[3]  # 当前年化利率
            if code in repo_codes and price:
                try:
                    rate = float(price)
                    if rate > 0:
                        repos.append({
                            'code': code,
                            'name': f'GC{repo_codes[code]}({code})',
                            'period': repo_codes[code],
                            'rate': round(rate, 3),
                            'type': '逆回购',
                        })
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"  [逆回购] 行情获取失败: {e}")

    # 兜底（非交易时间无行情）
    if not repos:
        repos = [
            {'code': '204001', 'name': 'GC001(1天)', 'period': '1天期', 'rate': None, 'type': '逆回购', 'note': '交易时间查看实时利率'},
            {'code': '204007', 'name': 'GC007(7天)', 'period': '7天期', 'rate': None, 'type': '逆回购', 'note': '月末/季末利率较高'},
            {'code': '204014', 'name': 'GC014(14天)', 'period': '14天期', 'rate': None, 'type': '逆回购', 'note': ''},
            {'code': '204028', 'name': 'GC028(28天)', 'period': '28天期', 'rate': None, 'type': '逆回购', 'note': ''},
        ]

    return {
        'title': '国债逆回购',
        'description': '无风险的短期现金管理工具，月末/季末/年末利率可达10-20%年化',
        'items': repos,
        'buy_criteria': '月末最后1-2天做1天期利率最高；平时做7天期性价比最好',
        'risk': '无风险',
        'tips': [
            '上午10:00前操作，利率通常更高',
            '月末/季末/年末最后一个交易日利率飙升，提前准备资金',
            '门槛：上交所10万起，深交所1000元起',
            '深交所代码：131810(1天)/131811(2天)/131800(3天)/131801(7天)',
        ],
    }
