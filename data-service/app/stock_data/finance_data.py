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
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/get?"
        "type=RPT_F10_FINANCE_MAINFINADATA&sty=ALL"
        f"&filter=(SECUCODE=%22{secucode}%22)"
        "&p=1&ps=5&sr=-1&st=REPORT_DATE"
    )
    data = _get_json(url)
    if data and data.get('result') and data['result'].get('data'):
        items = data['result']['data']
        for item in items:
            roe = _safe_float(item.get('ROEJQ'))
            if roe is not None:
                result['roe_list'].append(roe)
            gm = _safe_float(item.get('XSMLL'))
            if gm is not None:
                result['gross_margin_list'].append(gm)
            cr = _safe_float(item.get('JYXJLMLL'))
            if cr is not None:
                result['cash_ratio_list'].append(cr)
        if items:
            result['debt_ratio'] = _safe_float(items[0].get('ZCFZL'))


def _fetch_valuation(stock_code, market, result):
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
    except Exception:
        pass

    url = (
        f"https://push2.eastmoney.com/api/qt/stock/get?"
        f"secid={market}.{stock_code}&fields=f135"
    )
    data = _get_json(url)
    if data and data.get('data'):
        result['dividend_yield'] = _safe_float(data['data'].get('f135'))


def _fetch_dividends(secucode, result):
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/get?"
        "type=RPT_F10_SHAREBONUS&sty=ALL"
        f"&filter=(SECUCODE=%22{secucode}%22)(ASSIGN_PROGRESS=%222%22)"
        "&p=1&ps=10&sr=-1&st=EX_DIVIDEND_DATE"
    )
    data = _get_json(url)
    if data and data.get('result') and data['result'].get('data'):
        items = data['result']['data']
        years = set()
        for item in items:
            date_str = item.get('REPORT_DATE', '')
            if date_str:
                years.add(date_str[:4])
        if years:
            sorted_years = sorted(years, reverse=True)
            count = 1
            for i in range(1, len(sorted_years)):
                if int(sorted_years[i-1]) - int(sorted_years[i]) == 1:
                    count += 1
                else:
                    break
            result['continuous_dividend_years'] = count


def _safe_float(val):
    if val is None or val == '' or val == '-':
        return None
    try:
        v = float(val)
        return v if v != 0 else None
    except (ValueError, TypeError):
        return None
