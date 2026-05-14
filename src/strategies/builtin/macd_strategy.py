"""Built-in strategy: MACD golden cross / death cross / divergence."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, cross_above, cross_below, macd


class MACDStrategy(BaseStrategy):
    """Buy on MACD golden cross (DIF crosses above DEA), sell on death cross.

    Params:
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line period (default 9).
        require_below_zero: If True, only enter when DIF < 0 (bottom fishing).
        stop_loss_pct: Stop loss percentage (default 5.0).
    """

    name = "macd_strategy"
    display_name = "MACD 金叉"
    description = "MACD金叉买入，死叉卖出，可选零轴下方金叉"
    category = "trend"
    params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "require_below_zero": False,
        "stop_loss_pct": 5.0,
    }

    def get_required_indicators(self) -> List[str]:
        return ["macd_dif", "macd_dea", "macd_bar"]

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        dif, dea, _bar = macd(closes, self.params["fast"], self.params["slow"], self.params["signal"])

        if cross_above(dif, dea, idx):
            if self.params["require_below_zero"] and (dif[idx] is not None and dif[idx] > 0):
                return False, ""
            return True, f"MACD金叉 DIF={dif[idx]:.4f} 上穿 DEA={dea[idx]:.4f}"
        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        closes = _closes(data)
        dif, dea, _bar = macd(closes, self.params["fast"], self.params["slow"], self.params["signal"])
        stop_loss = self.params["stop_loss_pct"]

        if cross_below(dif, dea, idx):
            return True, f"MACD死叉 DIF={dif[idx]:.4f} 下穿 DEA={dea[idx]:.4f}"

        current = data[idx]["close"]
        if current < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["slow"] + self.params["signal"] + 5
