"""Technical indicator calculations for charts.py."""
import pandas as pd
import numpy as np

def calculate_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI = 100 - 100/(1+RS)，默认14日"""
    if len(closes) < period:
        return pd.Series(dtype=float)
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rs = rs.replace([np.inf, -np.inf], np.nan)
    return 100 - (100 / (1 + rs))

def calculate_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """返回 (macd_line, signal_line, histogram) 三元组"""
    if len(closes) < slow:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_kdj(highs: pd.Series, lows: pd.Series, closes: pd.Series,
                   n: int = 9, m1: int = 3, m2: int = 3):
    """KDJ(9,3,3) — 随机指标"""
    if len(closes) < n:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
    lowest_low = lows.rolling(n, min_periods=n).min()
    highest_high = highs.rolling(n, min_periods=n).max()
    rsv = (closes - lowest_low) / (highest_high - lowest_low) * 100
    rsv = rsv.replace([np.inf, -np.inf], np.nan)
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j

def calculate_wr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14):
    """Williams %R = (HHV - close) / (HHV - LLV) * 100，范围 [-100, 0]"""
    if len(closes) < period:
        return pd.Series(dtype=float)
    highest_high = highs.rolling(period, min_periods=period).max()
    lowest_low = lows.rolling(period, min_periods=period).min()
    result = (highest_high - closes) / (highest_high - lowest_low) * 100
    return result.replace([np.inf, -np.inf], np.nan)

def calculate_obv(closes: pd.Series, volumes: pd.Series) -> pd.Series:
    """OBV = 累计成交量（价格上升时加，下降时减）"""
    if len(closes) < 2:
        return pd.Series(0, index=closes.index)
    direction = np.sign(closes.diff())
    return (direction * volumes).cumsum()

def calculate_bollinger_bands(closes: pd.Series, period: int = 20, num_std: float = 2):
    """布林带 = MA ± num_std * STD"""
    if len(closes) < period:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
    mid = closes.rolling(period, min_periods=period).mean()
    std = closes.rolling(period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower