"""Built-in strategy: Mean reversion from extreme deviations."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, sma


class MeanRevertStrategy(BaseStrategy):
    """Buy when price deviates far below its moving average, expecting reversion.

    Params:
        period: MA period for mean estimation (default 20).
        deviation_pct: Entry below MA by this % (default 5.0).
        target_pct: Exit when price returns to within this % of MA (default 1.0).
        stop_loss_pct: Stop loss below entry (default 5.0).
    """

    name = "mean_revert"
    display_name = "均值回归"
    description = "价格偏离均线过大时逆势买入，回归卖出"
    category = "mean_reversion"
    params = {
        "period": 20,
        "deviation_pct": 5.0,
        "target_pct": 1.0,
        "stop_loss_pct": 5.0,
    }

    def get_required_indicators(self) -> List[str]:
        return [f"ma{self.params['period']}"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        ma = sma(closes, self.params["period"])
        curr = closes[idx]

        if ma[idx] is None:
            return False, ""

        deviation = (curr - ma[idx]) / ma[idx] * 100
        if deviation < -self.params["deviation_pct"]:
            return True, f"偏离MA{self.params['period']} {deviation:.1f}%，超跌反弹买入"

        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        ma = sma(closes, self.params["period"])
        curr = closes[idx]
        stop_loss = self.params["stop_loss_pct"]

        if ma[idx] is not None:
            deviation = abs(curr - ma[idx]) / ma[idx] * 100
            if deviation <= self.params["target_pct"]:
                return True, f"回归MA{self.params['period']}偏差{deviation:.1f}%，卖出"

        if curr < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["period"] + 1
