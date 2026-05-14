"""Built-in strategy: Trend following with MA alignment."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, sma


class TrendFollowStrategy(BaseStrategy):
    """Buy when short/medium/long MAs are in bullish alignment, sell when alignment breaks.

    Params:
        short: Short MA period (default 5).
        medium: Medium MA period (default 20).
        long: Long MA period (default 60).
        bias_limit: Max entry bias from short MA in percent (default 3.0, avoid chasing).
        stop_loss_pct: Stop loss (default 5.0).
    """

    name = "trend_follow"
    display_name = "趋势跟随"
    description = "多头排列时回踩买入，排列破坏卖出"
    category = "trend"
    params = {
        "short": 5,
        "medium": 20,
        "long": 60,
        "bias_limit": 3.0,
        "stop_loss_pct": 5.0,
    }

    def get_required_indicators(self) -> List[str]:
        return [f"ma{self.params['short']}", f"ma{self.params['medium']}", f"ma{self.params['long']}"]

    def _aligned(self, data: List[Dict], idx: int) -> bool:
        """Check bullish MA alignment: short > medium > long."""
        closes = _closes(data)
        s = sma(closes, self.params["short"])
        m = sma(closes, self.params["medium"])
        l = sma(closes, self.params["long"])
        vals = (s[idx], m[idx], l[idx])
        if None in vals:
            return False
        return s[idx] > m[idx] > l[idx]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        s = sma(closes, self.params["short"])
        curr = closes[idx]

        if not self._aligned(data, idx):
            return False, ""

        # Check bias — price should be near MA (pullback entry)
        if s[idx] is not None:
            bias = abs(curr - s[idx]) / s[idx] * 100
            if bias > self.params["bias_limit"]:
                return False, f"乖离{bias:.1f}% > {self.params['bias_limit']}%，不追高"

        return True, "多头排列回踩买入"

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        stop_loss = self.params["stop_loss_pct"]

        if not self._aligned(data, idx):
            return True, "多头排列破坏，卖出"

        current = data[idx]["close"]
        if current < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["long"] + 1
