"""Built-in strategy: Bollinger Bands breakout / mean reversion."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, bollinger_bands


class BollingerStrategy(BaseStrategy):
    """Buy when price touches lower band (mean reversion), sell at middle or upper band.

    Params:
        period: Bollinger period (default 20).
        std_mult: Standard deviation multiplier (default 2.0).
        sell_at_middle: If True, exit at middle band; else at upper band (default True).
        stop_loss_pct: Stop loss percentage (default 5.0).
    """

    name = "bollinger"
    display_name = "布林带"
    description = "触及下轨买入，回归中轨或上轨卖出"
    category = "mean_reversion"
    params = {
        "period": 20,
        "std_mult": 2.0,
        "sell_at_middle": True,
        "stop_loss_pct": 5.0,
    }

    def get_required_indicators(self) -> List[str]:
        return ["bollinger_upper", "bollinger_middle", "bollinger_lower"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        ma, upper, lower = bollinger_bands(closes, self.params["period"], self.params["std_mult"])
        curr = closes[idx]

        if lower[idx] is not None and curr <= lower[idx]:
            return True, f"触及布林下轨 {lower[idx]:.2f}，超卖反弹买入"
        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        ma, upper, lower = bollinger_bands(closes, self.params["period"], self.params["std_mult"])
        curr = closes[idx]
        stop_loss = self.params["stop_loss_pct"]

        target = ma[idx] if self.params["sell_at_middle"] else upper[idx]
        if target is not None and curr >= target:
            label = "中轨" if self.params["sell_at_middle"] else "上轨"
            return True, f"回归布林{label} {target:.2f}，卖出"

        if curr < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["period"] + 1
