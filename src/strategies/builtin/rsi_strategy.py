"""Built-in strategy: RSI oversold / overbought."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, rsi


class RSIStrategy(BaseStrategy):
    """Buy when RSI drops below oversold threshold, sell when above overbought.

    Params:
        period: RSI period (default 14).
        oversold: RSI level indicating oversold (default 30).
        overbought: RSI level indicating overbought (default 70).
        stop_loss_pct: Stop loss percentage (default 5.0).
    """

    name = "rsi_strategy"
    display_name = "RSI 超买超卖"
    description = "RSI超卖买入，超买卖出，配合止损"
    category = "mean_reversion"
    params = {"period": 14, "oversold": 30.0, "overbought": 70.0, "stop_loss_pct": 5.0}

    def get_required_indicators(self) -> List[str]:
        return ["rsi"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        rsi_vals = rsi(closes, self.params["period"])
        curr = rsi_vals[idx]
        if curr is None:
            return False, ""

        if curr < self.params["oversold"]:
            return True, f"RSI={curr:.1f} 进入超卖区，买入"
        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        rsi_vals = rsi(closes, self.params["period"])
        curr = rsi_vals[idx]
        stop_loss = self.params["stop_loss_pct"]

        if curr is not None and curr > self.params["overbought"]:
            return True, f"RSI={curr:.1f} 进入超买区，卖出"

        current = data[idx]["close"]
        if current < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["period"] + 2
