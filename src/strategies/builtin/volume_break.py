"""Built-in strategy: Volume breakout above resistance."""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.strategies.base import BaseStrategy, _closes, _volumes, sma


class VolumeBreakStrategy(BaseStrategy):
    """Buy when price breaks resistance on high volume. Sell on reversal below breakout.

    Params:
        vol_period: Volume MA period (default 5).
        vol_mult: Volume must be > N × average (default 2.0).
        resistance_lookback: Days to find resistance high (default 20).
        stop_loss_pct: Stop loss (default 3.0).
    """

    name = "volume_break"
    display_name = "放量突破"
    description = "放量突破阻力位买入，跌破突破位卖出"
    category = "volume"
    params = {
        "vol_period": 5,
        "vol_mult": 2.0,
        "resistance_lookback": 20,
        "stop_loss_pct": 3.0,
    }

    def get_required_indicators(self) -> List[str]:
        return ["volume_ratio", "resistance_level"]

    def _resistance(self, data: List[Dict], idx: int) -> float:
        """Find the highest close in the lookback window before idx."""
        start = max(0, idx - self.params["resistance_lookback"])
        window = data[start:idx]
        if not window:
            return float("inf")
        return max(d["high"] for d in window)

    def entry_signal(self, data: List[Dict], idx: int) -> Tuple[bool, str]:
        closes = _closes(data)
        vols = _volumes(data)
        vol_ma = sma(vols, self.params["vol_period"])

        curr_close = closes[idx]
        curr_vol = vols[idx]
        avg_vol = vol_ma[idx]
        resistance = self._resistance(data, idx)

        if avg_vol is None or curr_vol < avg_vol * self.params["vol_mult"]:
            return False, ""

        if curr_close > resistance:
            ratio = curr_vol / avg_vol if avg_vol > 0 else 0
            return True, f"放量{ratio:.1f}x突破阻力{resistance:.2f}，买入"

        return False, ""

    def exit_signal(
        self, data: List[Dict], idx: int, entry_idx: int, entry_price: float
    ) -> Tuple[bool, str]:
        stop_loss = self.params["stop_loss_pct"]
        resistance = self._resistance(data, entry_idx)
        curr_close = data[idx]["close"]

        if curr_close < resistance:
            return True, f"跌破突破位{resistance:.2f}，卖出"

        if curr_close < entry_price * (1 - stop_loss / 100):
            return True, f"止损 {stop_loss}%"

        return False, ""

    def _min_data_length(self) -> int:
        return self.params["resistance_lookback"] + 5
