"""K线图表生成模块

使用 mplfinance 生成 K线图表，支持 MA5/MA10/MA20 均线指标，
以及 RSI、MACD、Bollinger Bands、KDJ、WR、OBV 等技术指标。
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# === Indicator Definitions ===
# All supported indicators for use with mpf.make_addplot()
INDICATOR_DEFINITIONS = {
    "rsi": {"display_name": "RSI", "panel": 1, "yllabel": "RSI", "y_on_right": True},
    "macd": {"display_name": "MACD", "panel": 1, "yllabel": "MACD", "y_on_right": True},
    "bollinger": {"display_name": "BB", "panel": 0, "yllabel": "BB", "y_on_right": False},
    "kdj": {"display_name": "KDJ", "panel": 1, "yllabel": "KDJ", "y_on_right": True},
    "wr": {"display_name": "WR", "panel": 1, "yllabel": "WR", "y_on_right": True},
    "obv": {"display_name": "OBV", "panel": 1, "yllabel": "OBV", "y_on_right": True},
}

# Pre-computed mplfinance style objects (never change, so compute once)
_MPF_MARKET_COLORS = mpf.make_marketcolors(
    up="green", down="red", edge="inherit", wick="inherit", volume="in",
)
_MPF_STYLE = mpf.make_mpf_style(
    marketcolors=_MPF_MARKET_COLORS,
    gridstyle="-",
    gridcolor="#333333",
    facecolor="white",
    figcolor="white",
    y_on_right=True,
)
_MA_COLORS = {5: "purple", 10: "orange", 20: "blue"}
_DEFAULT_MA_PERIODS = [5, 10, 20]

# Default output directory (stable, not cwd-dependent)
CHART_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "charts_cache")


def format_volume(volume: float, code: str) -> str:
    """Format volume for display based on market type.

    A股/港股: >=1万 显示 "X.XX万"
    美股: 显示 "X.XXM" / "X.XXK"
    """
    if volume is None:
        return '---'
    try:
        v = float(volume)
        # A股/港股 use 万 (ten thousands)
        if code.startswith('hk') or (len(code) == 6 and code.isdigit() and not code.startswith('9')):
            if v >= 100000000:
                return f"{v/100000000:.1f}亿"
            elif v >= 10000:
                return f"{v/10000:.0f}万"
            return f"{v:.0f}"
        else:
            # US stocks use M/B notation
            if v >= 1000000000:
                return f"{v/1000000000:.1f}B"
            elif v >= 1000000:
                return f"{v/1000000:.1f}M"
            elif v >= 1000:
                return f"{v/1000:.1f}K"
            return f"{v:.0f}"
    except (ValueError, TypeError):
        return '---'


def convert_history_to_df(history_data: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    """
    将历史数据 dict 列表转换为 mplfinance 所需的 DataFrame 格式。

    Args:
        history_data: 股票历史数据列表，每项包含 date, open, high, low, close, volume, pct_chg

    Returns:
        DataFrame with Date index and OHLCV columns, or None if data is empty
    """
    if history_data is None or len(history_data) == 0:
        return None

    df = pd.DataFrame(history_data)

    # Determine date column (case-insensitive check)
    date_col = None
    for col in df.columns:
        if col.lower() == "date":
            date_col = col
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df.set_index(date_col, inplace=True)

    # 重命名列为 mplfinance 需要的格式
    column_mapping = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=column_mapping)

    # 只保留需要的 OHLCV 列
    ohlcv_columns = ["Open", "High", "Low", "Close", "Volume"]
    # 只选择存在的列
    existing_columns = [c for c in ohlcv_columns if c in df.columns]
    df = df[existing_columns]

    return df


def add_ma_indicators(df: pd.DataFrame, ma_periods: List[int] = None) -> pd.DataFrame:
    """
    为 DataFrame 添加 MA 均线指标。

    Args:
        df: OHLCV DataFrame
        ma_periods: 均线周期列表，默认 [5, 10, 20]

    Returns:
        添加了 MA5, MA10, MA20 列的 DataFrame
    """
    if ma_periods is None:
        ma_periods = _DEFAULT_MA_PERIODS

    df = df.copy()

    for period in ma_periods:
        ma_col = f"MA{period}"
        df[ma_col] = df["Close"].rolling(window=period).mean()

    return df


# === Technical Indicator Calculations ===
# Import from shared package for TUI/GUI code reuse
from src.shared.indicators import (
    calculate_rsi as _calc_rsi,
    calculate_macd as _calc_macd,
    calculate_bollinger_bands as _calc_bollinger,
    calculate_kdj as _calc_kdj,
    calculate_wr as _calc_wr,
    calculate_obv as _calc_obv,
    calculate_fibonacci_levels,
    find_support_resistance,
)


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)."""
    return _calc_rsi(df["Close"], period)


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Calculate MACD (matches original charts.py convention)."""
    macd_line, signal_line, histogram = _calc_macd(df["Close"], fast, slow, signal)
    # Original convention: MACD = (DIF - DEA) * 2
    macd_histogram = (macd_line - signal_line) * 2
    return pd.DataFrame({"MACD": macd_histogram, "DIF": macd_line, "DEA": signal_line}, index=df.index)


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Calculate Bollinger Bands."""
    upper, middle, lower = _calc_bollinger(df["Close"], period, std_dev)
    return pd.DataFrame({"BB_UPPER": upper, "BB_MIDDLE": middle, "BB_LOWER": lower}, index=df.index)


def calculate_kdj(df: pd.DataFrame, period: int = 9, smooth_k: int = 3, smooth_d: int = 3) -> pd.DataFrame:
    """Calculate KDJ."""
    k, d, j = _calc_kdj(df["High"], df["Low"], df["Close"], period, smooth_k, smooth_d)
    return pd.DataFrame({"K": k, "D": d, "J": j}, index=df.index)


def calculate_wr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate WR."""
    return _calc_wr(df["High"], df["Low"], df["Close"], period)


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """Calculate OBV."""
    return _calc_obv(df["Close"], df["Volume"])


def add_indicators(df: pd.DataFrame, indicator_names: List[str]) -> pd.DataFrame:
    """
    为 DataFrame 添加多个技术指标。

    Args:
        df: OHLCV DataFrame
        indicator_names: 指标名称列表，支持: rsi, macd, bollinger, kdj, wr, obv

    Returns:
        添加了指定指标列的 DataFrame
    """
    df = df.copy()

    for name in indicator_names:
        name_lower = name.lower()
        if name_lower == "rsi":
            df["RSI"] = calculate_rsi(df)
        elif name_lower == "macd":
            macd_df = calculate_macd(df)
            df["MACD"] = macd_df["MACD"]
            df["DIF"] = macd_df["DIF"]
            df["DEA"] = macd_df["DEA"]
        elif name_lower == "bollinger":
            bb_df = calculate_bollinger_bands(df)
            df["BB_UPPER"] = bb_df["BB_UPPER"]
            df["BB_MIDDLE"] = bb_df["BB_MIDDLE"]
            df["BB_LOWER"] = bb_df["BB_LOWER"]
        elif name_lower == "kdj":
            kdj_df = calculate_kdj(df)
            df["K"] = kdj_df["K"]
            df["D"] = kdj_df["D"]
            df["J"] = kdj_df["J"]
        elif name_lower == "wr":
            df["WR"] = calculate_wr(df)
        elif name_lower == "obv":
            df["OBV"] = calculate_obv(df)

    return df


def create_kline_chart(
    data: List[Dict[str, Any]],
    code: str,
    days: int = 60,
    output_dir: Optional[str] = None,
    indicators: Optional[List[str]] = None,
    draw_sr: bool = False,
    draw_fibonacci: bool = False,
) -> str:
    """
    创建 K线图表并保存为 PNG 文件。

    Args:
        data: 股票历史数据列表
        code: 股票代码
        days: 显示的天数（默认60天）
        output_dir: 输出目录，默认使用 charts_cache 目录
        indicators: 技术指标列表，支持 rsi, macd, bollinger, kdj, wr, obv
        draw_sr: 是否绘制支撑/阻力位
        draw_fibonacci: 是否绘制斐波那契回调线

    Returns:
        保存的图表文件路径
    """
    # 确定输出目录
    if output_dir is None:
        output_dir = CHART_CACHE_DIR

    os.makedirs(output_dir, exist_ok=True)

    # 转换数据
    df = convert_history_to_df(data)
    if df is None or len(df) == 0:
        raise ValueError("No data available for chart")

    # 只取最后 days 天的数据
    if len(df) > days:
        df = df.tail(days)

    # 添加 MA 均线指标
    df = add_ma_indicators(df)

    # 准备 MA 叠加数据（只添加有有效值的 MA 线）
    ma_plots = []
    for period in _DEFAULT_MA_PERIODS:
        ma_col = f"MA{period}"
        if ma_col in df.columns and len(df) >= period:
            ma_plots.append(mpf.make_addplot(df[ma_col], color=_MA_COLORS.get(period, "gray"), width=0.8))

    # 添加技术指标
    all_plots = list(ma_plots)
    panel_ratios = "(4, 2)"
    if indicators:
        df = add_indicators(df, indicators)

        for ind_name in indicators:
            ind_lower = ind_name.lower()
            if ind_lower == "rsi":
                all_plots.append(mpf.make_addplot(df["RSI"], panel=1, ylabel="RSI", y_on_right=True, color="purple", width=1.0))
            elif ind_lower == "macd":
                all_plots.append(mpf.make_addplot(df["MACD"], panel=1, ylabel="MACD", y_on_right=True, color="blue", width=1.0))
                all_plots.append(mpf.make_addplot(df["DIF"], panel=1, ylabel="MACD", y_on_right=True, color="orange", width=0.8))
                all_plots.append(mpf.make_addplot(df["DEA"], panel=1, ylabel="MACD", y_on_right=True, color="purple", width=0.8))
                panel_ratios = "(4, 2, 1)"
            elif ind_lower == "bollinger":
                all_plots.append(mpf.make_addplot(df["BB_UPPER"], color="gray", linestyle="--", width=0.5))
                all_plots.append(mpf.make_addplot(df["BB_MIDDLE"], color="blue", width=0.5))
                all_plots.append(mpf.make_addplot(df["BB_LOWER"], color="gray", linestyle="--", width=0.5))
            elif ind_lower == "kdj":
                all_plots.append(mpf.make_addplot(df["K"], panel=1, ylabel="KDJ", y_on_right=True, color="red", width=1.0))
                all_plots.append(mpf.make_addplot(df["D"], panel=1, ylabel="KDJ", y_on_right=True, color="blue", width=1.0))
                all_plots.append(mpf.make_addplot(df["J"], panel=1, ylabel="KDJ", y_on_right=True, color="purple", linestyle="--", width=0.8))
                panel_ratios = "(4, 2, 1)"
            elif ind_lower == "wr":
                all_plots.append(mpf.make_addplot(df["WR"], panel=1, ylabel="WR", y_on_right=True, color="orange", width=1.0))
            elif ind_lower == "obv":
                all_plots.append(mpf.make_addplot(df["OBV"], panel=1, ylabel="OBV", y_on_right=True, color="brown", width=1.0))

    # 支撑/阻力位叠加
    if draw_sr:
        sr_levels = find_support_resistance(df)
        for level in sr_levels['support']:
            all_plots.append(mpf.make_addplot(
                pd.Series(level, index=df.index),
                panel=0, color='green', linestyle='dashed', width=0.8,
                secondary_y=False
            ))
        for level in sr_levels['resistance']:
            all_plots.append(mpf.make_addplot(
                pd.Series(level, index=df.index),
                panel=0, color='red', linestyle='dashed', width=0.8,
                secondary_y=False
            ))

    # 斐波那契回调线叠加
    if draw_fibonacci:
        high = df['High'].max()
        low = df['Low'].min()
        fib_levels = calculate_fibonacci_levels(high, low)
        for label, level in fib_levels.items():
            all_plots.append(mpf.make_addplot(
                pd.Series(level, index=df.index),
                panel=0, color='orange', linestyle='dotted', width=0.5,
                secondary_y=False
            ))

    # 绘制图表
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=_MPF_STYLE,
        title=f"{code} - K线 (MA5/MA10/MA20)",
        ylabel="价格",
        ylabel_lower="成交量",
        volume=True,
        figsize=(10, 6),
        returnfig=True,
        panel_ratios=(4, 2),
        addplot=all_plots if all_plots else None,
    )

    # 保存到文件
    chart_filename = f"kline_{code}_{days}d.png"
    chart_path = os.path.join(output_dir, chart_filename)

    try:
        fig.savefig(chart_path, format="png", dpi=80, facecolor="white")
    finally:
        plt.close(fig)

    logger.info(f"K线图表已保存: {chart_path}")

    return chart_path