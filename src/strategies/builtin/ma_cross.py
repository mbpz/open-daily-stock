"""Built-in strategy: MA Golden Cross / Death Cross."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, cross_above, cross_below, sma


class MACrossStrategy(BaseStrategy):
    """Golden cross (MA fast > MA slow) entry, death cross exit.

    Params:
        fast: Fast MA period (default 5).
        slow: Slow MA period (default 20).
        stop_loss_pct: Stop loss percentage from entry (default 5.0).
    """

    name = "ma_cross"
    display_name = "均线金叉"
    description = "MA快线上穿慢线买入，下穿卖出，配合止损"
    category = "trend"
    params = {"fast": 5, "slow": 20, "stop_loss_pct": 5.0}

    def get_required_indicators(self) -> List[str]:
        return [f"ma{self.params['fast']}", f"ma{self.params['slow']}"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        fast = sma(closes, self.params["fast"])
        slow = sma(closes, self.params["slow"])

        if cross_above(fast, slow, idx):
            return True, f"MA{self.params['fast']}上穿MA{self.params['slow']}，金叉买入"
        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        fast = sma(closes, self.params["fast"])
        slow = sma(closes, self.params["slow"])
        stop_loss = self.params["stop_loss_pct"]

        # Death cross
        if cross_below(fast, slow, idx):
            return True, f"MA{self.params['fast']}下穿MA{self.params['slow']}，死叉卖出"

        # Stop loss
        current = data[idx]["close"]
        if current < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%（{entry_price:.2f}→{current:.2f}）"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["slow"] + 1
