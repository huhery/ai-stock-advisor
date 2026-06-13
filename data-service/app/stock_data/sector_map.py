"""股票板块映射 — 通过东方财富接口获取股票所属行业板块

实时从东方财富获取个股所属行业，缓存到内存中避免重复请求。
"""
import requests
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 内存缓存：{stock_code: sector_name}
_sector_cache = {}


def get_sector(stock_code):
    """获取单只股票的所属行业板块

    优先从缓存读取，缓存不命中则查接口。
    """
    if stock_code in _sector_cache:
        return _sector_cache[stock_code]

    # 从东方财富个股接口获取行业
    sector = _fetch_sector_from_eastmoney(stock_code)
    if sector:
        _sector_cache[stock_code] = sector
    return sector or ''


def get_sectors_batch(stock_codes):
    """批量获取股票板块，返回 {code: sector} 字典

    使用东方财富板块列表接口，一次性拉取所有行业板块的成分股，
    反向建立 code → sector 映射。
    """
    # 如果缓存已经足够，直接返回
    uncached = [c for c in stock_codes if c not in _sector_cache]
    if not uncached:
        return {c: _sector_cache.get(c, '') for c in stock_codes}

    # 尝试批量获取
    _fetch_all_sectors()

    return {c: _sector_cache.get(c, '') for c in stock_codes}


def _fetch_sector_from_eastmoney(stock_code):
    """从东方财富获取单只股票的行业分类"""
    try:
        # 东方财富个股信息接口
        if stock_code.startswith('6'):
            secid = f"1.{stock_code}"
        else:
            secid = f"0.{stock_code}"

        url = (
            f"http://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}&fields=f127"
        )
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            sector = data.get('f127', '')
            if sector and sector != '-':
                return sector
    except Exception:
        pass
    return ''


def _fetch_all_sectors():
    """从东方财富拉取行业板块列表，建立 code → sector 映射

    使用行业板块接口，获取所有行业及其成分股代码。
    """
    try:
        # 东方财富行业板块列表
        url = (
            "http://82.push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
            "&fltt=2&invt=2&fid=f3"
            "&fs=m:90+t:2"  # 行业板块
            "&fields=f12,f14"
        )
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return

        data = resp.json().get('data', {}).get('diff', [])
        if not data:
            return

        # 对每个行业板块，获取其成分股
        for item in data[:50]:  # 最多处理50个行业
            sector_code = item.get('f12', '')
            sector_name = item.get('f14', '')
            if not sector_code or not sector_name:
                continue

            _fetch_sector_stocks(sector_code, sector_name)
            time.sleep(0.2)

    except Exception:
        pass


def _fetch_sector_stocks(sector_code, sector_name):
    """获取某个行业板块下的所有成分股"""
    try:
        url = (
            f"http://82.push2.eastmoney.com/api/qt/clist/get"
            f"?pn=1&pz=500&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
            f"&fltt=2&invt=2&fid=f3"
            f"&fs=b:{sector_code}+f:!50"
            f"&fields=f12"
        )
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code != 200:
            return

        stocks = resp.json().get('data', {}).get('diff', [])
        if not stocks:
            return

        for stock in stocks:
            code = stock.get('f12', '')
            if code:
                _sector_cache[code] = sector_name

    except Exception:
        pass


# 备用：硬编码的常见股票板块映射（东方财富接口不可用时兜底）
FALLBACK_SECTORS = {
    '600519': '白酒', '000858': '白酒', '600809': '白酒', '000568': '白酒', '002304': '白酒',
    '600036': '银行', '601318': '保险', '601166': '银行', '601398': '银行', '601288': '银行',
    '601939': '银行', '601328': '银行', '601988': '银行', '600000': '银行', '601998': '银行',
    '601658': '银行', '000001': '银行', '600016': '银行', '002142': '银行',
    '000333': '家电', '000651': '家电', '600690': '家电', '000921': '家电',
    '300750': '新能源', '601012': '新能源',
    '600900': '电力', '601669': '电力',
    '002475': '消费电子', '000725': '消费电子',
    '600031': '机械', '601766': '机械',
    '601888': '旅游', '600276': '医药', '600887': '乳业',
    '300059': '互联网', '002352': '物流', '600585': '建材',
    '002714': '养殖', '000002': '地产',
    '600028': '石化', '601857': '石化', '600500': '化工',
    '601088': '煤炭', '600111': '有色', '603993': '有色',
    '600050': '通信', '601138': '电子', '000636': '电子',
    '000063': '通信', '000100': '家电',
    '300015': '医疗', '300124': '自动化',
    '688981': '半导体', '002409': '半导体',
    '601601': '保险', '601628': '保险',
    '601211': '券商', '600030': '券商',
    '600332': '医药', '600206': '新材料',
    '600060': '家电', '603650': '化工',
    '600228': '互联网', '600186': '食品',
    '600322': '地产', '300505': '化工',
    '002001': '化工', '600703': '光电',
    '601766': '机械', '601800': '建筑',
}


def get_sector_with_fallback(stock_code):
    """获取板块，优先用接口，失败用兜底映射"""
    sector = get_sector(stock_code)
    if not sector:
        sector = FALLBACK_SECTORS.get(stock_code, '')
    return sector
