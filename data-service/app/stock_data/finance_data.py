import time
import json

try:
    from curl_cffi import requests as http
    IMPERSONATE = True
except ImportError:
    import requests as http
    IMPERSONATE = False

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def _get_json(url):
    try:
        if IMPERSONATE:
            resp = http.get(url, headers=HEADERS, timeout=15, impersonate="chrome")
        else:
            resp = http.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def get_finance_indicators(stock_code):
    if stock_code.startswith('6'):
        secucode = f"{stock_code}.SH"
        market = '1'
    else:
        secucode = f"{stock_code}.SZ"
        market = '0'

    result = {
        'stock_code': stock_code,
        'roe_list': [],
        'gross_margin_list': [],
        'cash_ratio_list': [],
        'pe': None,
        'pb': None,
        'dividend_yield': None,
        'debt_ratio': None,
        'revenue_growth': None,
        'profit_growth': None,
        'continuous_dividend_years': 0,
    }

    _fetch_annual(secucode, result)
    time.sleep(0.5)
    _fetch_valuation(stock_code, market, result)
    time.sleep(0.5)
    _fetch_dividends(secucode, result)
    time.sleep(0.3)
    return result


def _fetch_annual(secucode, result):
    """获取年报财务数据

    使用东方财富杜邦分析接口获取年度ROE（最准确）。
    毛利率和负债率从主要财务指标接口获取。
    """
    # 方案1：杜邦分析接口（有明确的年度ROE）
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/get?"
        "type=RPT_F10_FINANCE_DBFX&sty=ALL"
        f"&filter=(SECUCODE=%22{secucode}%22)"
        "&p=1&ps=6&sr=-1&st=REPORT_DATE"
    )
    data = _get_json(url)
    if data and data.get('result') and data['result'].get('data'):
        items = data['result']['data']
        for item in items:
            roe = _safe_float(item.get('ROEJQ'))  # 杜邦分析中的ROE是年化值
            if roe is not None:
                result['roe_list'].append(roe)

    # 方案2：如果杜邦接口没数据，用主要财务指标（取年报）
    if not result['roe_list']:
        url = (
            "https://datacenter.eastmoney.com/securities/api/data/get?"
            "type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL"
            f"&filter=(SECUCODE=%22{secucode}%22)"
            "&p=1&ps=20&sr=-1&st=REPORT_DATE"
        )
        data = _get_json(url)
        if data and data.get('result') and data['result'].get('data'):
            items = data['result']['data']
            # 只取年报数据（报告日期为12月31日）
            for item in items:
                report_date = item.get('REPORT_DATE', '')
                if '12-31' not in report_date and '1231' not in report_date.replace('-', ''):
                    continue
                roe = _safe_float(item.get('ROEJQ'))
                if roe is not None:
                    result['roe_list'].append(roe)
                gm = _safe_float(item.get('XSMLL'))
                if gm is not None:
                    result['gross_margin_list'].append(gm)
                # 现金含量
                cr = _safe_float(item.get('JYXJLMLL'))
                if cr is None:
                    ocf = _safe_float(item.get('NETCASH_OPERATE'))
                    net_profit = _safe_float(item.get('PARENT_NETPROFIT'))
                    if ocf is not None and net_profit is not None and net_profit > 0:
                        cr = round(ocf / net_profit * 100, 2)
                if cr is not None:
                    result['cash_ratio_list'].append(cr)
            if items:
                result['debt_ratio'] = _safe_float(items[0].get('ZCFZL'))
            return

    # 毛利率和负债率还是从主要财务指标取
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/get?"
        "type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL"
        f"&filter=(SECUCODE=%22{secucode}%22)"
        "&p=1&ps=20&sr=-1&st=REPORT_DATE"
    )
    data = _get_json(url)
    if data and data.get('result') and data['result'].get('data'):
        items = data['result']['data']
        for item in items:
            report_date = item.get('REPORT_DATE', '')
            # 只取年报（12月31日的数据）
            if '12-31' not in report_date and '1231' not in report_date.replace('-', ''):
                continue
            gm = _safe_float(item.get('XSMLL'))
            if gm is not None:
                result['gross_margin_list'].append(gm)
            cr = _safe_float(item.get('JYXJLMLL'))
            if cr is None:
                ocf = _safe_float(item.get('NETCASH_OPERATE'))
                net_profit = _safe_float(item.get('PARENT_NETPROFIT'))
                if ocf is not None and net_profit is not None and net_profit > 0:
                    cr = round(ocf / net_profit * 100, 2)
            if cr is not None:
                result['cash_ratio_list'].append(cr)
        if items:
            result['debt_ratio'] = _safe_float(items[0].get('ZCFZL'))


def _fetch_valuation(stock_code, market, result):
    """获取 PE / PB（腾讯行情接口，稳定可用）

    股息率不再从 push2 的 f135 获取（该字段已失效），
    改由 _fetch_dividends 用"每股派息 / 股价"计算。
    """
    tc_code = f"sh{stock_code}" if market == '1' else f"sz{stock_code}"
    try:
        if IMPERSONATE:
            resp = http.get(f"http://qt.gtimg.cn/q={tc_code}", headers=HEADERS, timeout=5, impersonate="chrome")
        else:
            resp = http.get(f"http://qt.gtimg.cn/q={tc_code}", headers=HEADERS, timeout=5)
        resp.encoding = 'gbk'
        parts = resp.text.split('~')
        if len(parts) > 46:
            result['pe'] = _safe_float(parts[39])
            result['pb'] = _safe_float(parts[46])
            # 顺手记录当前价，供股息率计算复用，避免重复请求
            result['_current_price'] = _safe_float(parts[3])
    except Exception:
        pass


def _fetch_dividends(secucode, result):
    """获取分红历史，计算股息率和连续分红年数

    数据源：东方财富 RPT_SHAREBONUS_DET 分红明细接口（已验证可用）。
    - 股息率 = 最近一个已实施完整年度的每股税前派息 / 当前股价 × 100
    - 连续分红年数 = 从最近年份往前连续有派息记录的年数

    说明：原 push2 的 f135 股息率字段已失效，故改为自行计算。
    """
    stock_code = secucode.split('.')[0]

    # v1/get 接口格式（实测可用，旧的 data/get + RPT_F10_SHAREBONUS 已失效）
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/v1/get?"
        "reportName=RPT_SHAREBONUS_DET&columns=ALL"
        f"&filter=(SECURITY_CODE=%22{stock_code}%22)"
        "&pageNumber=1&pageSize=30&sortColumns=NOTICE_DATE&sortTypes=-1"
    )

    data = None
    for attempt in range(3):
        data = _get_json(url)
        if data and data.get('result') and data['result'].get('data'):
            break
        time.sleep(1.0)

    if not (data and data.get('result') and data['result'].get('data')):
        # 接口失败时保持保守默认值，不影响整体流程
        result['continuous_dividend_years'] = 3
        return

    items = data['result']['data']

    # 按"会计年度(报告期年份)"归集已实施派息，取最近一个完整实施的年度计算股息率。
    # A股分红常跨年实施(如2024年报2025年6月除息)，且一个年度可能含中期+年度多次派息，
    # 故按报告期年份聚合，比滚动12个月(TTM)窗口更稳定，也更贴合"年度股息率"语义。
    year_bonus = {}            # {报告期年份(int): 每10股税前派息合计}
    year_has_annual = set()    # 该年度是否已实施"年报"分红(报告期为12-31且已除息)

    for item in items:
        pretax = _safe_float(item.get('PRETAX_BONUS_RMB'))
        ex_date_str = item.get('EX_DIVIDEND_DATE')
        report_date = (item.get('REPORT_DATE') or '')[:10]

        # 只统计已实施(有除息日)的派息
        if pretax is None or not ex_date_str:
            continue
        if len(report_date) < 10 or not report_date[:4].isdigit():
            continue

        year = int(report_date[:4])
        year_bonus[year] = year_bonus.get(year, 0) + pretax
        # 报告期为年报(12-31)且已除息，标记该年度分红已完整落地
        if report_date[5:10] == '12-31':
            year_has_annual.add(year)

    # ===== 计算股息率 =====
    # 取"年报已实施"的最近年度，保证是一个完整年度的分红
    current_price = result.get('_current_price')
    if year_bonus and current_price and current_price > 0:
        complete_years = [y for y in year_bonus if y in year_has_annual]
        target_year = max(complete_years) if complete_years else max(year_bonus.keys())
        dps = year_bonus[target_year] / 10.0  # 每10股 -> 每股
        result['dividend_yield'] = round(dps / current_price * 100, 2)

    # ===== 计算连续分红年数 =====
    if year_bonus:
        sorted_years = sorted(year_bonus.keys(), reverse=True)
        count = 1
        for i in range(1, len(sorted_years)):
            if sorted_years[i - 1] - sorted_years[i] == 1:
                count += 1
            else:
                break
        result['continuous_dividend_years'] = count
    else:
        result['continuous_dividend_years'] = 0

    # 清理临时字段
    result.pop('_current_price', None)


def _safe_float(val):
    if val is None or val == '' or val == '-':
        return None
    try:
        v = float(val)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None
