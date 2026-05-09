"""K线图表生成模块

使用 mplfinance 生成 K线图表，支持 MA5/MA10/MA20 均线指标。
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def convert_history_to_df(history_data: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    """
    将历史数据 dict 列表转换为 mplfinance 所需的 DataFrame 格式。

    Args:
        history_data: 股票历史数据列表，每项包含 date, open, high, low, close, volume, pct_chg

    Returns:
        DataFrame with Date index and OHLCV columns, or None if data is empty
    """
    if not history_data:
        return None

    df = pd.DataFrame(history_data)

    # 确保日期列是 datetime 类型并设为索引
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

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
        ma_periods = [5, 10, 20]

    df = df.copy()

    for period in ma_periods:
        ma_col = f"MA{period}"
        df[ma_col] = df["Close"].rolling(window=period).mean()

    return df


def create_kline_chart(
    data: List[Dict[str, Any]],
    code: str,
    days: int = 60,
    output_dir: Optional[str] = None,
) -> str:
    """
    创建 K线图表并保存为 PNG 文件。

    Args:
        data: 股票历史数据列表
        code: 股票代码
        days: 显示的天数（默认60天）
        output_dir: 输出目录，默认使用 charts_cache 目录

    Returns:
        保存的图表文件路径
    """
    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), "charts_cache")

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

    # 设置 mplfinance 样式
    mc = mpf.make_marketcolors(
        up="green",
        down="red",
        edge="inherit",
        wick="inherit",
        volume="in",
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle="-",
        gridcolor="#333333",
        facecolor="white",
        figcolor="white",
        y_on_right=True,
    )

    # 准备 MA 叠加数据（只添加有有效值的 MA 线）
    ma_plots = []
    for period in [5, 10, 20]:
        ma_col = f"MA{period}"
        if ma_col in df.columns:
            # 检查是否有有效值（非全 NaN）
            if df[ma_col].notna().any():
                color_map = {5: "purple", 10: "orange", 20: "blue"}
                ma_plots.append(mpf.make_addplot(df[ma_col], color=color_map.get(period, "gray"), width=0.8))

    # 绘制图表
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        title=f"{code} - K线 (MA5/MA10/MA20)",
        ylabel="价格",
        ylabel_lower="成交量",
        volume=True,
        figsize=(10, 6),
        returnfig=True,
        panel_ratios=(4, 2),
        addplot=ma_plots if ma_plots else None,
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