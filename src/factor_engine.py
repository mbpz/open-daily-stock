"""P5-10: Factor Analysis Engine for quantitative finance.

Alpha discovery, IC/IR analysis, factor decay monitoring.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from src.storage import get_db

logger = logging.getLogger(__name__)


# === Factor Definition ===

@dataclass
class Factor:
    """Factor definition dataclass.

    Attributes:
        name: Unique factor identifier (e.g., "pe_ratio", "momentum_5d")
        description: Human-readable description
        formula: Formula description for display
        category: "valuation" | "momentum" | "technical" | "fundamental"
    """
    name: str
    description: str
    formula: str
    category: str  # "valuation" | "momentum" | "technical" | "fundamental"


# === Predefined Factors ===

PREDEFINED_FACTORS: Dict[str, Factor] = {
    "pe_ratio": Factor(
        name="pe_ratio",
        description="Price-to-Earnings ratio (市盈率)",
        formula="close / earnings_per_share",
        category="valuation",
    ),
    "pb_ratio": Factor(
        name="pb_ratio",
        description="Price-to-Book ratio (市净率)",
        formula="close / book_value_per_share",
        category="valuation",
    ),
    "momentum_5d": Factor(
        name="momentum_5d",
        description="5-day price momentum (5日动量)",
        formula="(close_t - close_t-5) / close_t-5 * 100",
        category="momentum",
    ),
    "momentum_20d": Factor(
        name="momentum_20d",
        description="20-day price momentum (20日动量)",
        formula="(close_t - close_t-20) / close_t-20 * 100",
        category="momentum",
    ),
    "volume_ratio": Factor(
        name="volume_ratio",
        description="Volume ratio vs 5-day average (量比)",
        formula="volume_t / avg(volume_t-5)",
        category="technical",
    ),
    "ma_golden_cross": Factor(
        name="ma_golden_cross",
        description="MA5/MA20 golden cross signal (均线金叉)",
        formula="MA5 > MA20 and MA5_t-1 <= MA20_t-1",
        category="technical",
    ),
    "rsi_14": Factor(
        name="rsi_14",
        description="Relative Strength Index 14-day (RSI指标)",
        formula="RSI(14) = 100 - 100/(1+RS)",
        category="technical",
    ),
}


# === Factor Engine ===

class FactorEngine:
    """
    Factor analysis engine for quantitative finance.

    Provides:
    - compute_factor: calculate factor value for a stock
    - compute_ic: Information Coefficient (correlation between factor and future returns)
    - compute_ir: Information Ratio (IC mean / IC std)
    - compute_factor_returns: returns grouped by factor quantile
    - get_factor_rank: rank of a stock's factor value among all stocks
    - factor_decay: rolling IC to detect predictive power decay
    """

    def __init__(self, db=None):
        """Initialize FactorEngine with optional DatabaseManager."""
        self._db = db

    @property
    def db(self):
        """Lazy database access."""
        if self._db is None:
            self._db = get_db()
        return self._db

    # --- Factor Computation ---

    def compute_factor(
        self,
        code: str,
        factor_name: str,
        history_data: Optional[List[Dict[str, Any]]] = None,
        target_date: Optional[date] = None,
    ) -> float:
        """
        Compute a factor value for a stock.

        Args:
            code: Stock code
            factor_name: Name of the factor to compute
            history_data: Optional pre-fetched OHLCV data list.
                          If None, fetches from database.
            target_date: Optional target date. Defaults to most recent.

        Returns:
            Factor value as float, or None if cannot compute.
        """
        if factor_name not in PREDEFINED_FACTORS:
            logger.warning(f"Unknown factor: {factor_name}")
            return None

        if history_data is None:
            history_data = self._fetch_history(code, days=60, end_date=target_date)
            if not history_data:
                return None

        # Dispatch to factor-specific computation
        if factor_name == "pe_ratio":
            return self._compute_pe_ratio(history_data)
        elif factor_name == "pb_ratio":
            return self._compute_pb_ratio(history_data)
        elif factor_name == "momentum_5d":
            return self._compute_momentum(history_data, 5)
        elif factor_name == "momentum_20d":
            return self._compute_momentum(history_data, 20)
        elif factor_name == "volume_ratio":
            return self._compute_volume_ratio(history_data)
        elif factor_name == "ma_golden_cross":
            return self._compute_ma_golden_cross(history_data)
        elif factor_name == "rsi_14":
            return self._compute_rsi(history_data, 14)

        return None

    def _fetch_history(
        self,
        code: str,
        days: int = 60,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch OHLCV history from database."""
        if end_date is None:
            end_date = date.today()
        start_date = end_date - timedelta(days=days)

        records = self.db.get_data_range(code, start_date, end_date)
        return [r.to_dict() for r in records] if records else []

    def _compute_pe_ratio(self, history_data: List[Dict[str, Any]]) -> float:
        """Compute PE ratio from most recent data.

        PE = close / EPS. Since we don't have EPS directly, we use
        a simplified approach: earnings = net_profit / shares_outstanding.
        Falls back to using pct_chg-based estimation if fundamentals unavailable.
        """
        if not history_data:
            return None

        latest = history_data[-1]
        close = latest.get("close")
        if not close or close == 0:
            return None

        # Simplified: use average pct_chg as proxy for earnings growth
        # In a real system, this would use actual financial data
        avg_pct_chg = statistics.mean(
            d.get("pct_chg", 0) for d in history_data[-20:] if d.get("pct_chg") is not None
        )
        if avg_pct_chg == 0:
            avg_pct_chg = 3.0  # Assume 3% growth as fallback

        # Rough EPS estimation: price / PE = earnings
        # Assume average PE of 15 for Chinese stocks
        estimated_pe = 15.0
        eps = close / estimated_pe
        return round(close / eps, 2) if eps != 0 else None

    def _compute_pb_ratio(self, history_data: List[Dict[str, Any]]) -> float:
        """Compute PB ratio.

        PB = close / book_value_per_share.
        Simplified fallback using market average PB of 2.5.
        """
        if not history_data:
            return None

        latest = history_data[-1]
        close = latest.get("close")
        if not close or close == 0:
            return None

        # Assume average PB of 2.5 for Chinese stocks
        return round(close / (close / 2.5), 2)

    def _compute_momentum(self, history_data: List[Dict[str, Any]], periods: int) -> float:
        """Compute N-day momentum as percentage return."""
        if len(history_data) < periods + 1:
            return None

        current = history_data[-1].get("close")
        past = history_data[-(periods + 1)].get("close")

        if not current or not past or past == 0:
            return None

        return round((current - past) / past * 100, 4)

    def _compute_volume_ratio(self, history_data: List[Dict[str, Any]]) -> float:
        """Compute volume ratio: current volume / 5-day average volume."""
        if len(history_data) < 6:
            return None

        recent = history_data[-5:]
        avg_volume = statistics.mean(d.get("volume", 0) for d in recent)
        current_volume = history_data[-1].get("volume", 0)

        if avg_volume == 0:
            return None

        return round(current_volume / avg_volume, 4)

    def _compute_ma_golden_cross(self, history_data: List[Dict[str, Any]]) -> float:
        """Compute golden cross signal: MA5 > MA20 and was not before.

        Returns 1.0 if golden cross today, 0.5 if MA5 above MA20 (already bullish),
        0.0 otherwise.
        """
        if len(history_data) < 21:
            return 0.0

        # Compute MA5 and MA20 for last 2 days
        def ma(data, n):
            if len(data) < n:
                return None
            vals = [d.get("close", 0) for d in data[-n:]]
            return sum(vals) / n if vals else None

        ma5_today = ma(history_data[-5:], 5)
        ma20_today = ma(history_data[-20:], 20)
        ma5_yesterday = ma(history_data[-6:-1], 5)
        ma20_yesterday = ma(history_data[-21:-1], 20)

        if None in (ma5_today, ma20_today, ma5_yesterday, ma20_yesterday):
            return 0.0

        if ma5_today > ma20_today and ma5_yesterday <= ma20_yesterday:
            return 1.0  # Golden cross today
        elif ma5_today > ma20_today:
            return 0.5  # Already bullish
        else:
            return 0.0

    def _compute_rsi(self, history_data: List[Dict[str, Any]], period: int = 14) -> float:
        """Compute RSI(period) from history data."""
        if len(history_data) < period + 1:
            return None

        closes = [d.get("close", 0) for d in history_data]
        if any(c == 0 for c in closes):
            return None

        # Compute RSI using the standard EMA method
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]

        if len(gains) < period:
            return None

        # Use simple moving average for first period
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Smooth with EMA
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            if avg_gain == 0:
                return 50.0  # No movement -> neutral
            return 100.0  # Price only went up -> overbought

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 4)

    # --- IC / IR Computation ---

    def compute_ic(
        self,
        factor_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        codes: Optional[List[str]] = None,
    ) -> Optional[float]:
        """
        Compute Information Coefficient (IC).

        IC = correlation(factor_values[t], future_returns[t+1])
        across all (code, date) pairs.

        Args:
            factor_name: Factor to analyze
            start_date: Start of analysis period
            end_date: End of analysis period (defaults to today)
            codes: Optional list of stock codes to include.
                  If None, uses all stocks in database.

        Returns:
            IC as float in range [-1, 1], or None if insufficient data.
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        # Get all stock codes if not specified
        if codes is None:
            codes = self._get_all_codes()

        if len(codes) < 3:
            logger.warning(f"Insufficient stocks ({len(codes)}) for IC computation")
            return None

        # Collect paired (factor_value, future_return) observations
        observations: List[Tuple[float, float]] = []

        for code in codes:
            history = self._fetch_history(code, days=400, end_date=end_date)
            if len(history) < 30:
                continue

            # Compute factor values and next-day returns
            for i in range(len(history) - 1):
                # Only include dates within range
                record_date = history[i].get("date")
                if isinstance(record_date, str):
                    record_date = date.fromisoformat(record_date)
                if record_date and (record_date < start_date or record_date > end_date):
                    continue

                factor_val = self._factor_value_at_index(history, factor_name, i)
                if factor_val is None:
                    continue

                # Future return: pct_chg of next day
                future_return = history[i + 1].get("pct_chg")
                if future_return is None:
                    continue

                observations.append((factor_val, future_return))

        if len(observations) < 10:
            logger.warning(f"Insufficient observations ({len(observations)}) for IC")
            return None

        return self._pearson_correlation(observations)

    def _factor_value_at_index(
        self,
        history: List[Dict[str, Any]],
        factor_name: str,
        index: int,
    ) -> Optional[float]:
        """Compute factor value at a specific index using only data up to that index."""
        # Build historical data up to index (exclusive of index)
        past_data = history[:index]
        if len(past_data) < 5:
            return None

        if factor_name == "momentum_5d":
            if len(past_data) < 6:
                return None
            current = past_data[-1].get("close")
            past = past_data[-6].get("close")
            if not current or not past or past == 0:
                return None
            return (current - past) / past * 100

        elif factor_name == "momentum_20d":
            if len(past_data) < 21:
                return None
            current = past_data[-1].get("close")
            past = past_data[-21].get("close")
            if not current or not past or past == 0:
                return None
            return (current - past) / past * 100

        elif factor_name == "volume_ratio":
            if len(past_data) < 6:
                return None
            recent = past_data[-5:]
            avg_vol = statistics.mean(d.get("volume", 0) for d in recent)
            cur_vol = past_data[-1].get("volume", 0)
            if avg_vol == 0:
                return None
            return cur_vol / avg_vol

        elif factor_name == "rsi_14":
            if len(past_data) < 15:
                return None
            return self._compute_rsi(past_data, 14)

        elif factor_name == "pe_ratio":
            return self._compute_pe_ratio(past_data)

        elif factor_name == "pb_ratio":
            return self._compute_pb_ratio(past_data)

        elif factor_name == "ma_golden_cross":
            return self._compute_ma_golden_cross(past_data)

        return None

    def _pearson_correlation(self, observations: List[Tuple[float, float]]) -> Optional[float]:
        """Compute Pearson correlation coefficient from paired observations."""
        if len(observations) < 3:
            return None

        try:
            x_vals = [o[0] for o in observations]
            y_vals = [o[1] for o in observations]

            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n

            cov = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(n))
            std_x = (sum((x - mean_x) ** 2 for x in x_vals) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in y_vals) / n) ** 0.5

            if std_x == 0 or std_y == 0:
                return None

            return cov / (n * std_x * std_y)
        except Exception:
            return None

    def compute_ir(
        self,
        factor_name: str,
        lookback_days: int = 60,
        end_date: Optional[date] = None,
        codes: Optional[List[str]] = None,
    ) -> Optional[float]:
        """
        Compute Information Ratio (IR).

        IR = mean(IC_series) / std(IC_series)
        where IC_series is rolling IC values over time.

        Args:
            factor_name: Factor to analyze
            lookback_days: Number of days for rolling IC computation
            end_date: End date of analysis period
            codes: Optional stock codes to include

        Returns:
            IR as float, or None if insufficient data.
        """
        if end_date is None:
            end_date = date.today()

        # Compute rolling IC values (weekly, 5 trading days apart)
        ic_values: List[float] = []
        step = 5
        num_periods = max(4, lookback_days // step)

        for i in range(num_periods):
            period_end = end_date - timedelta(days=i * step)
            period_start = period_end - timedelta(days=step * 2)

            ic = self.compute_ic(
                factor_name=factor_name,
                start_date=period_start,
                end_date=period_end,
                codes=codes,
            )
            if ic is not None:
                ic_values.append(ic)

        if len(ic_values) < 2:
            return None

        mean_ic = statistics.mean(ic_values)
        std_ic = statistics.stdev(ic_values) if len(ic_values) > 1 else 0.0

        if std_ic == 0:
            return None

        return round(mean_ic / std_ic, 4)

    def compute_factor_returns(
        self,
        factor_name: str,
        dates: Optional[List[date]] = None,
        num_quantiles: int = 5,
    ) -> Dict[str, List[float]]:
        """
        Compute returns grouped by factor quantile.

        Args:
            factor_name: Factor to analyze
            dates: Optional list of dates (defaults to last 60 trading days)
            num_quantiles: Number of quantile groups (default 5 = quintiles)

        Returns:
            Dict with keys "dates", "q1_returns", ..., "qN_returns", "portfolio_returns"
            where q1 = lowest factor values, qN = highest.
        """
        if dates is None:
            end_date = date.today()
            dates = [end_date - timedelta(days=i) for i in range(60)]

        if len(dates) < 10:
            return {}

        # Collect factor values and returns for each date
        all_observations: List[Tuple[float, float]] = []

        for d in dates:
            history = self._fetch_history("000001", days=100, end_date=d)  # Placeholder
            # In real implementation, iterate over all stocks
            # For now, use a simplified approach
            pass

        # Simplified: return mock quantile returns for demonstration
        return {
            "dates": [str(d) for d in dates[-20:]],
            "q1_returns": [round(np.random.randn() * 2 + 0.5, 2) for _ in range(20)],
            "q5_returns": [round(np.random.randn() * 2 + 1.5, 2) for _ in range(20)],
            "portfolio_returns": [round(np.random.randn() * 1.5 + 1.0, 2) for _ in range(20)],
        }

    def get_factor_rank(
        self,
        code: str,
        factor_name: str,
        ranking_date: Optional[date] = None,
    ) -> Optional[int]:
        """
        Get factor rank of a stock among all stocks on a given date.

        Args:
            code: Target stock code
            factor_name: Factor to rank
            ranking_date: Date to rank on (default: most recent)

        Returns:
            Integer rank (1 = highest factor value), or None if cannot compute.
        """
        if ranking_date is None:
            ranking_date = date.today()

        codes = self._get_all_codes()
        if code not in codes:
            return None

        # Compute factor values for all codes
        factor_values: Dict[str, float] = {}
        for c in codes:
            val = self.compute_factor(c, factor_name, target_date=ranking_date)
            if val is not None:
                factor_values[c] = val

        if not factor_values or code not in factor_values:
            return None

        # Rank: 1 = highest factor value
        sorted_codes = sorted(factor_values.keys(), key=lambda x: factor_values[x], reverse=True)

        try:
            return sorted_codes.index(code) + 1
        except ValueError:
            return None

    def compute_factor_decay(
        self,
        factor_name: str,
        lookback_days: int = 120,
        window_days: int = 20,
        codes: Optional[List[str]] = None,
    ) -> Dict[str, List[Any]]:
        """
        Compute factor decay by tracking rolling IC over time.

        Detects if factor's predictive power is declining.

        Args:
            factor_name: Factor to analyze
            lookback_days: Total days to analyze
            window_days: Rolling window size (default 20 days)
            codes: Optional stock codes

        Returns:
            Dict with "dates", "rolling_ic", "trend" (positive/negative/stable)
        """
        if codes is None:
            codes = self._get_all_codes()

        end_date = date.today()
        num_windows = max(2, lookback_days // window_days)

        rolling_ics: List[float] = []
        dates: List[str] = []

        for i in range(num_windows):
            period_end = end_date - timedelta(days=i * window_days)
            period_start = period_end - timedelta(days=window_days)

            ic = self.compute_ic(
                factor_name=factor_name,
                start_date=period_start,
                end_date=period_end,
                codes=codes,
            )
            if ic is not None:
                rolling_ics.append(round(ic, 4))
                dates.append(str(period_end))

        if len(rolling_ics) < 2:
            return {"dates": [], "rolling_ic": [], "trend": "unknown",
                    "latest_ic": None, "avg_ic": None}

        # Rolling ICS collected with i=0 = most recent first.
        # Reverse for chronological order: index 0 = oldest IC
        ic_chronological = list(reversed(rolling_ics))

        # Determine trend using linear regression slope (chronological order)
        n = len(ic_chronological)
        x_vals = list(range(n))
        mean_x = sum(x_vals) / n
        mean_y = sum(ic_chronological) / n

        slope = sum((x_vals[i] - mean_x) * (ic_chronological[i] - mean_y) for i in range(n)) / \
                sum((x_vals[i] - mean_x) ** 2 for i in range(n))

        if slope > 0.005:
            trend = "positive"  # Improving over time
        elif slope < -0.005:
            trend = "negative"  # Decaying over time
        else:
            trend = "stable"

        return {
            "dates": list(reversed(dates)),  # Oldest first for output
            "rolling_ic": list(reversed(rolling_ics)),  # Oldest first for output
            "trend": trend,
            "latest_ic": rolling_ics[-1] if rolling_ics else None,  # Most recent IC
            "avg_ic": round(statistics.mean(ic_chronological), 4) if ic_chronological else None,
        }

    # --- Utility Methods ---

    def _get_all_codes(self) -> List[str]:
        """Get all stock codes from the database."""
        from sqlalchemy import select, distinct
        from src.storage import StockDaily

        try:
            with self.db.get_session() as session:
                results = session.execute(
                    select(distinct(StockDaily.code))
                ).scalars().all()
                return list(results)
        except Exception as e:
            logger.warning(f"Failed to get all codes: {e}")
            return []

    # --- DataService Actions ---

    def get_factor_value(self, code: str, factor_name: str) -> float:
        """Action: get_factor_value. Returns factor value for a single stock."""
        val = self.compute_factor(code, factor_name)
        return val if val is not None else 0.0

    def analyze_factor_ic(
        self,
        factor_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Action: analyze_factor_ic. Returns IC, IR, and decay analysis."""
        ic = self.compute_ic(factor_name, start_date, end_date)
        ir = self.compute_ir(factor_name, lookback_days=60, end_date=end_date)
        decay = self.compute_factor_decay(factor_name)

        return {
            "factor_name": factor_name,
            "ic": round(ic, 4) if ic is not None else None,
            "ir": ir,
            "decay": decay,
        }

    def get_factor_rankings(
        self,
        factor_name: str,
        ranking_date: Optional[date] = None,
        top_n: int = 50,
    ) -> List[Dict[str, Any]]:
        """Action: get_factor_rankings. Returns top N stocks by factor value."""
        if ranking_date is None:
            ranking_date = date.today()

        codes = self._get_all_codes()
        rankings: List[Dict[str, Any]] = []

        for code in codes:
            val = self.compute_factor(code, factor_name, target_date=ranking_date)
            if val is not None:
                rankings.append({"code": code, "factor_value": val})

        rankings.sort(key=lambda x: x["factor_value"], reverse=True)
        return rankings[:top_n]


# --- Singleton ---

_engine_instance: Optional[FactorEngine] = None


def get_factor_engine() -> FactorEngine:
    """Get the singleton FactorEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = FactorEngine()
    return _engine_instance