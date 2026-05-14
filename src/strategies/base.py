"""Base strategy classes and indicator helpers for P6-1 strategy engine."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trade signal
# ---------------------------------------------------------------------------

@dataclass
class TradeSignal:
    """A single trade decision."""
    date: str
    action: str  # "buy" | "sell"
    price: float
    shares: int = 100
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "action": self.action,
            "price": self.price,
            "shares": self.shares,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Base strategy
# ---------------------------------------------------------------------------

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    Subclasses implement entry_signal() and exit_signal().
    The default generate_trades() iterates over data day-by-day,
    calling these methods at each step.
    """

    name: str = "base"
    display_name: str = "Base Strategy"
    description: str = ""
    category: str = "custom"  # trend | momentum | mean_reversion | volume | custom

    # Tunable parameters (override in subclasses)
    params: Dict[str, Any] = {}

    def __init__(self, **kwargs):
        """Initialize with optional parameter overrides."""
        self.params = {**self.__class__.params, **kwargs}

    # ---- abstract interface ----

    @abstractmethod
    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        """Check if entry conditions are met at the given index.

        Args:
            data: Full OHLCV data list (each dict has date/open/high/low/close/volume/pct_chg).
            idx: Current index to evaluate.

        Returns:
            (should_enter, reason_string)
        """
        ...

    @abstractmethod
    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        """Check if exit conditions are met at the given index.

        Args:
            data: Full OHLCV data list.
            idx: Current index.
            entry_idx: Index where position was entered.
            entry_price: Entry price.

        Returns:
            (should_exit, reason_string)
        """
        ...

    # ---- optional overrides ----

    def get_required_indicators(self) -> List[str]:
        """Return list of indicator names needed by this strategy."""
        return []

    def get_params(self) -> Dict[str, Any]:
        """Return all tunable parameters (for hyperparameter optimization)."""
        return dict(self.params)

    # ---- trade generation (default loop) ----

    def generate_trades(self, data: List[Dict]) -> List[Dict]:
        """Generate trade signals from OHLCV data.

        Default implementation: iterate day-by-day, track position,
        call entry_signal() when flat, exit_signal() when long.

        Override for strategies with different state machines
        (e.g., grid trading, multi-leg).
        """
        if len(data) < self._min_data_length():
            return []

        trades: List[Dict] = []
        position: Optional[int] = None  # None = flat, idx = entry index
        entry_price: float = 0.0

        for i in range(self._min_data_length(), len(data)):
            if position is None:
                enter, reason = self.entry_signal(data, i)
                if enter:
                    price = data[i]["close"]
                    trades.append({
                        "date": data[i]["date"],
                        "action": "buy",
                        "price": price,
                        "shares": 100,
                        "reason": reason,
                    })
                    position = i
                    entry_price = price
            else:
                exit_sig, reason = self.exit_signal(data, i, position, entry_price)
                if exit_sig:
                    price = data[i]["close"]
                    trades.append({
                        "date": data[i]["date"],
                        "action": "sell",
                        "price": price,
                        "shares": 100,
                        "reason": reason,
                    })
                    position = None
                    entry_price = 0.0

        # Force exit at end of data if still holding
        if position is not None:
            last = data[-1]
            trades.append({
                "date": last["date"],
                "action": "sell",
                "price": last["close"],
                "shares": 100,
                "reason": "end of data",
            })

        return trades

    def _min_data_length(self) -> int:
        """Minimum number of data points needed before generating signals."""
        return 20

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.display_name})"


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

def _closes(data: List[Dict]) -> List[float]:
    return [d["close"] for d in data]


def _highs(data: List[Dict]) -> List[float]:
    return [d["high"] for d in data]


def _lows(data: List[Dict]) -> List[float]:
    return [d["low"] for d in data]


def _volumes(data: List[Dict]) -> List[float]:
    return [d.get("volume", 0) for d in data]


def sma(values: List[float], period: int) -> List[Optional[float]]:
    """Simple Moving Average. Returns None for indices < period-1."""
    result: List[Optional[float]] = []
    window_sum = 0.0
    for i, v in enumerate(values):
        window_sum += v
        if i >= period:
            window_sum -= values[i - period]
        if i >= period - 1:
            result.append(window_sum / period)
        else:
            result.append(None)
    return result


def ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average."""
    result: List[Optional[float]] = []
    multiplier = 2.0 / (period + 1)
    ema_val: Optional[float] = None
    for i, v in enumerate(values):
        if i == 0:
            ema_val = v
        else:
            ema_val = (v - ema_val) * multiplier + ema_val
        if i >= period - 1:
            result.append(ema_val)
        else:
            result.append(None)
    return result


def rsi(values: List[float], period: int = 14) -> List[Optional[float]]:
    """Relative Strength Index."""
    if len(values) < period + 1:
        return [None] * len(values)

    result: List[Optional[float]] = [None] * period
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains.append(delta if delta > 0 else 0)
        losses.append(-delta if delta < 0 else 0)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    rs_val = avg_gain / avg_loss if avg_loss != 0 else float("inf")
    result.append(100.0 - 100.0 / (1.0 + rs_val) if avg_loss != 0 else 100.0)

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs_val = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs_val))

    return result


def macd(
    values: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """MACD indicator. Returns (dif, dea, bar)."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)

    dif: List[Optional[float]] = []
    for i in range(len(values)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif.append(ema_fast[i] - ema_slow[i])
        else:
            dif.append(None)

    # DEA = EMA of DIF
    dea_vals: List[Optional[float]] = [None] * len(values)
    bar: List[Optional[float]] = [None] * len(values)

    # Find first valid DIF
    valid_start = None
    for i, d in enumerate(dif):
        if d is not None:
            valid_start = i
            break
    if valid_start is None:
        return dif, dea_vals, bar

    # Calculate DEA
    multiplier = 2.0 / (signal + 1)
    dea_running: Optional[float] = None
    for i in range(valid_start, len(values)):
        if dif[i] is None:
            continue
        if dea_running is None:
            dea_running = dif[i]
        else:
            dea_running = (dif[i] - dea_running) * multiplier + dea_running
        if i >= valid_start + slow + signal - 2:
            dea_vals[i] = dea_running
            bar_val = (dif[i] - dea_running) * 2
            bar[i] = bar_val

    return dif, dea_vals, bar


def bollinger_bands(
    values: List[float], period: int = 20, std_mult: float = 2.0
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Bollinger Bands. Returns (middle, upper, lower)."""
    ma = sma(values, period)
    upper: List[Optional[float]] = [None] * len(values)
    lower: List[Optional[float]] = [None] * len(values)

    for i in range(len(values)):
        if ma[i] is None:
            continue
        start = i - period + 1
        window = values[start : i + 1]
        mean_val = ma[i]
        variance = sum((v - mean_val) ** 2 for v in window) / period
        std = variance ** 0.5
        upper[i] = mean_val + std_mult * std
        lower[i] = mean_val - std_mult * std

    return ma, upper, lower


def kdj(
    highs: List[float], lows: List[float], closes: List[float],
    n: int = 9, m1: int = 3, m2: int = 3,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """KDJ indicator. Returns (k, d, j)."""
    k_vals: List[Optional[float]] = [None] * len(closes)
    d_vals: List[Optional[float]] = [None] * len(closes)
    j_vals: List[Optional[float]] = [None] * len(closes)

    rsv_list: List[Optional[float]] = [None] * len(closes)
    for i in range(n - 1, len(closes)):
        hh = max(highs[i - n + 1 : i + 1])
        ll = min(lows[i - n + 1 : i + 1])
        if hh == ll:
            rsv_list[i] = 50.0
        else:
            rsv_list[i] = (closes[i] - ll) / (hh - ll) * 100.0

    # K = EMA of RSV, D = EMA of K, J = 3*K - 2*D
    k_prev = 50.0
    d_prev = 50.0
    for i in range(len(closes)):
        if rsv_list[i] is None:
            continue
        k_val = (rsv_list[i] - k_prev) * (2.0 / (m1 + 1)) + k_prev
        d_val = (k_val - d_prev) * (2.0 / (m2 + 1)) + d_prev
        j_val = 3.0 * k_val - 2.0 * d_val
        k_vals[i] = round(k_val, 2)
        d_vals[i] = round(d_val, 2)
        j_vals[i] = round(j_val, 2)
        k_prev = k_val
        d_prev = d_val

    return k_vals, d_vals, j_vals


def cross_above(short: List[Optional[float]], long: List[Optional[float]], idx: int) -> bool:
    """Check if short crosses above long at index idx (compared to idx-1)."""
    if idx < 1:
        return False
    prev_s = short[idx - 1]
    prev_l = long[idx - 1]
    curr_s = short[idx]
    curr_l = long[idx]
    if None in (prev_s, prev_l, curr_s, curr_l):
        return False
    return prev_s <= prev_l and curr_s > curr_l


def cross_below(short: List[Optional[float]], long: List[Optional[float]], idx: int) -> bool:
    """Check if short crosses below long at index idx (compared to idx-1)."""
    if idx < 1:
        return False
    prev_s = short[idx - 1]
    prev_l = long[idx - 1]
    curr_s = short[idx]
    curr_l = long[idx]
    if None in (prev_s, prev_l, curr_s, curr_l):
        return False
    return prev_s >= prev_l and curr_s < curr_l
