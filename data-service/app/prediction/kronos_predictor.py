"""Kronos K线预测封装

基于 Kronos 基础模型（https://github.com/shiyu-coder/Kronos），
预测个股未来走势用于选股打分。

使用 Kronos-base（102M 参数）在 GPU 上推理，
输入最近 60 天日线 K 线，预测未来 5~10 天走势。

安装方式：
  cd data-service
  git clone https://github.com/shiyu-coder/Kronos.git vendor/kronos
"""
import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 将 Kronos 仓库加入 Python path
_kronos_path = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'kronos')
if os.path.exists(_kronos_path):
    sys.path.insert(0, os.path.abspath(_kronos_path))

# Kronos 模型实例（延迟加载，避免启动时占用显存）
_predictor = None
_model_loaded = False


def _ensure_model_loaded():
    """确保 Kronos 模型已加载到 GPU"""
    global _predictor, _model_loaded
    if _model_loaded:
        return _predictor is not None

    _model_loaded = True
    try:
        from model import Kronos, KronosTokenizer, KronosPredictor
        import torch

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"[{datetime.now()}] 正在加载 Kronos 模型（设备: {device}）...")

        # 根据是否有 GPU 选择模型大小
        if device == "cuda:0":
            model_name = "NeoQuasar/Kronos-base"  # 102M，GPU 推荐
        else:
            model_name = "NeoQuasar/Kronos-mini"  # 4.1M，CPU 友好

        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-2k")
        model = Kronos.from_pretrained(model_name)
        _predictor = KronosPredictor(model, tokenizer, device=device, max_context=512)
        print(f"[{datetime.now()}] Kronos 模型加载完成（{model_name}, {device}）")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Kronos 模型加载失败: {e}")
        _predictor = None
        return False


def predict_stock(kline_df, pred_days=5):
    """预测单只股票未来走势

    @param kline_df: DataFrame，包含列 ['日期', '开盘', '最高', '最低', '收盘', '成交量']
                     至少需要 60 行数据
    @param pred_days: 预测天数，默认 5 天
    @return: dict，包含预测涨跌幅等信息；None 表示预测失败
    """
    if not _ensure_model_loaded():
        return None

    if kline_df is None or len(kline_df) < 30:
        return None

    try:
        # 转换为 Kronos 需要的格式
        df = pd.DataFrame({
            'open': kline_df['开盘'].values,
            'high': kline_df['最高'].values,
            'low': kline_df['最低'].values,
            'close': kline_df['收盘'].values,
            'volume': kline_df['成交量'].astype(float).values,
        })

        lookback = len(df)
        # 生成时间戳（Kronos 需要 timestamp 列，用日期序列即可）
        base_date = pd.Timestamp('2026-01-01')
        x_timestamp = pd.Series([base_date + timedelta(days=i) for i in range(lookback)])
        y_timestamp = pd.Series([base_date + timedelta(days=lookback + i) for i in range(pred_days)])

        # 推理
        pred_df = _predictor.predict(
            df=df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_days,
            T=0.8,
            top_p=0.9,
            sample_count=3,  # 采样3次取均值，提高稳定性
            verbose=False
        )

        if pred_df is None or pred_df.empty:
            return None

        # 计算预测涨幅
        current_close = float(df['close'].iloc[-1])
        pred_close_final = float(pred_df['close'].iloc[-1])
        pred_close_max = float(pred_df['close'].max())
        pred_change_pct = (pred_close_final - current_close) / current_close * 100
        pred_max_change_pct = (pred_close_max - current_close) / current_close * 100

        return {
            'pred_change_pct': round(pred_change_pct, 2),
            'pred_max_change_pct': round(pred_max_change_pct, 2),
            'pred_close': round(pred_close_final, 2),
            'pred_days': pred_days,
        }

    except Exception as e:
        # 单只股票预测失败不影响整体流程
        return None


def predict_batch(kline_list, pred_days=5):
    """批量预测多只股票

    @param kline_list: list of (stock_code, kline_df) 元组
    @param pred_days: 预测天数
    @return: dict，{stock_code: predict_result}
    """
    if not _ensure_model_loaded():
        return {}

    results = {}
    # 准备批量数据
    valid_items = []
    for code, kline_df in kline_list:
        if kline_df is None or len(kline_df) < 30:
            continue
        valid_items.append((code, kline_df))

    if not valid_items:
        return {}

    # 尝试用 predict_batch（如果 Kronos 支持）
    try:
        df_list = []
        x_ts_list = []
        y_ts_list = []
        codes = []

        # 统一 lookback 长度（取最小值，或截断到统一长度）
        min_len = min(len(kdf) for _, kdf in valid_items)
        lookback = min(min_len, 512)  # Kronos max_context=512

        base_date = pd.Timestamp('2026-01-01')
        x_timestamp = pd.Series([base_date + timedelta(days=i) for i in range(lookback)])
        y_timestamp = pd.Series([base_date + timedelta(days=lookback + i) for i in range(pred_days)])

        for code, kline_df in valid_items:
            # 截取最后 lookback 行
            kdf = kline_df.tail(lookback).reset_index(drop=True)
            df = pd.DataFrame({
                'open': kdf['开盘'].values,
                'high': kdf['最高'].values,
                'low': kdf['最低'].values,
                'close': kdf['收盘'].values,
                'volume': kdf['成交量'].astype(float).values,
            })
            df_list.append(df)
            x_ts_list.append(x_timestamp)
            y_ts_list.append(y_timestamp)
            codes.append(code)

        # 调用 Kronos batch 预测
        pred_df_list = _predictor.predict_batch(
            df_list=df_list,
            x_timestamp_list=x_ts_list,
            y_timestamp_list=y_ts_list,
            pred_len=pred_days,
            T=0.8,
            top_p=0.9,
            sample_count=1,
            verbose=False
        )

        for i, pred_df in enumerate(pred_df_list):
            if pred_df is None or pred_df.empty:
                continue
            code = codes[i]
            current_close = float(df_list[i]['close'].iloc[-1])
            pred_close_final = float(pred_df['close'].iloc[-1])
            pred_close_max = float(pred_df['close'].max())
            pred_change_pct = (pred_close_final - current_close) / current_close * 100
            pred_max_change_pct = (pred_close_max - current_close) / current_close * 100

            results[code] = {
                'pred_change_pct': round(pred_change_pct, 2),
                'pred_max_change_pct': round(pred_max_change_pct, 2),
                'pred_close': round(pred_close_final, 2),
                'pred_days': pred_days,
            }

        return results

    except Exception as e:
        print(f"  [Kronos] 批量预测异常，回退到逐个预测: {e}")
        # 回退：逐个预测
        for code, kline_df in valid_items:
            result = predict_stock(kline_df, pred_days)
            if result:
                results[code] = result
        return results


def score_prediction(pred_result):
    """将预测结果转换为选股得分（0~100）

    @param pred_result: predict_stock() 的返回值
    @return: 得分 0~100
    """
    if not pred_result:
        return 0

    change = pred_result['pred_change_pct']
    max_change = pred_result['pred_max_change_pct']

    # 综合考虑最终涨幅和过程中最大涨幅
    if change >= 8:
        return 95
    elif change >= 5:
        return 85
    elif change >= 3:
        return 70
    elif change >= 1:
        return 50
    elif change >= 0:
        return 30
    elif change >= -3:
        return 10
    else:
        # 预测下跌，给 0 分
        return 0
