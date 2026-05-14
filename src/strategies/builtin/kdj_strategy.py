"""Built-in strategy: KDJ golden cross / death cross."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import (
    BaseStrategy, _closes, _highs, _lows, cross_above, cross_below, kdj
)


class KDJStrategy(BaseStrategy):
    """Buy on KDJ golden cross (K crosses above D), sell on death cross.

    Params:
        n: RSV period (default 9).
        m1: K smoothing (default 3).
        m2: D smoothing (default 3).
        oversold_entry: Only enter if K < this threshold (default 30).
        overbought_exit: Exit if K > this threshold (default 70).
        stop_loss_pct: Stop loss percentage (default 5.0).
    """

    name = "kdj_strategy"
    display_name = "KDJ 金叉"
    description = "KDJ金叉买入，死叉卖出，超卖区金叉优先"
    category = "mean_reversion"
    params = {
        "n": 9,
        "m1": 3,
        "m2": 3,
        "oversold_entry": 30.0,
        "overbought_exit": 70.0,
        "stop_loss_pct": 5.0,
    }

    def get_required_indicators(self) -> List[str]:
        return ["k", "d", "j"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        highs = _highs(data)
        lows = _lows(data)
        k_vals, d_vals, j_vals = kdj(
            highs, lows, closes,
            self.params["n"], self.params["m1"], self.params["m2"],
        )

        k = k_vals[idx]
        d = d_vals[idx]
        if k is None or d is None:
            return False, ""

        if cross_above(k_vals, d_vals, idx):
            if k > self.params["oversold_entry"]:
                return False, f"K={k:.1f} > {self.params['oversold_entry']}，不在超卖区"
            return True, f"KDJ超卖区金叉 K={k:.1f} D={d:.1f}"

        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        highs = _highs(data)
        lows = _lows(data)
        k_vals, d_vals, j_vals = kdj(
            highs, lows, closes,
            self.params["n"], self.params["m1"], self.params["m2"],
        )
        stop_loss = self.params["stop_loss_pct"]

        k = k_vals[idx]
        d = d_vals[idx]

        if k is not None and d is not None:
            if cross_below(k_vals, d_vals, idx):
                return True, f"KDJ死叉 K={k:.1f} D={d:.1f}"
            if k > self.params["overbought_exit"]:
                return True, f"K={k:.1f} 进入超买区"

        current = data[idx]["close"]
        if current < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["n"] + self.params["m1"] + self.params["m2"] + 2
