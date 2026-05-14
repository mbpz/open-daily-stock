"""Tests for P6-1 strategy engine: BaseStrategy, builtins, backtester integration."""
import pytest
import random
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_data():
    """Generate 120 days of mock OHLCV data."""
    random.seed(42)
    base = 50.0
    data = []
    for i in range(120):
        change = random.gauss(0.001, 0.02)
        base = base * (1 + change)
        data.append({
            "date": f"2025-{1+i//30:02d}-{1+i%30:02d}",
            "open": round(base * 0.99, 2),
            "high": round(base * 1.02, 2),
            "low": round(base * 0.98, 2),
            "close": round(base, 2),
            "volume": random.randint(5_000_000, 20_000_000),
            "pct_chg": round(change * 100, 2),
        })
    return data


@pytest.fixture
def trending_up_data():
    """Generate trending-up data for bullish strategy tests."""
    base = 50.0
    data = []
    for i in range(120):
        change = 0.005  # Steady uptrend
        base = base * (1 + change)
        data.append({
            "date": f"2025-{1+i//30:02d}-{1+i%30:02d}",
            "open": round(base * 0.99, 2),
            "high": round(base * 1.02, 2),
            "low": round(base * 0.98, 2),
            "close": round(base, 2),
            "volume": 10_000_000,
            "pct_chg": 0.5,
        })
    return data


# ---------------------------------------------------------------------------
# BaseStrategy
# ---------------------------------------------------------------------------

class TestBaseStrategy:
    def test_generate_trades_empty_data(self):
        from src.strategies.builtin import MACrossStrategy
        s = MACrossStrategy()
        trades = s.generate_trades([])
        assert trades == []

    def test_generate_trades_insufficient_data(self):
        from src.strategies.builtin import MACrossStrategy
        s = MACrossStrategy()
        trades = s.generate_trades([{"close": 10}] * 10)
        assert trades == []

    def test_min_data_length(self):
        from src.strategies.builtin import MACrossStrategy, TrendFollowStrategy
        assert MACrossStrategy()._min_data_length() == 21  # slow + 1
        assert TrendFollowStrategy()._min_data_length() == 61  # long + 1


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

class TestIndicators:
    def test_sma(self):
        from src.strategies.base import sma
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = sma(values, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 2.0  # (1+2+3)/3
        assert result[3] == 3.0  # (2+3+4)/3
        assert result[4] == 4.0  # (3+4+5)/3

    def test_rsi(self):
        from src.strategies.base import rsi
        # Upward trend → RSI should be high
        values = list(range(10, 30))
        result = rsi(values, 14)
        assert result[-1] is not None
        assert 50 < result[-1] <= 100

    def test_cross_above(self):
        from src.strategies.base import sma, cross_above
        short = [None, None, 5.0, 6.0]
        long = [None, None, 5.5, 5.5]
        assert cross_above(short, long, 3)
        assert not cross_above(short, long, 2)

    def test_cross_below(self):
        from src.strategies.base import sma, cross_below
        short = [None, None, 5.0, 4.0]
        long = [None, None, 4.5, 4.5]
        assert cross_below(short, long, 3)
        assert not cross_below(short, long, 2)

    def test_macd(self):
        from src.strategies.base import macd
        values = [10 + i * 0.1 for i in range(100)]
        dif, dea, bar = macd(values)
        assert dif[-1] is not None
        assert dea[-1] is not None
        assert bar[-1] is not None

    def test_bollinger_bands(self):
        from src.strategies.base import bollinger_bands
        values = [50 + random.gauss(0, 2) for _ in range(30)]
        ma, upper, lower = bollinger_bands(values, 20)
        assert ma[-1] is not None
        assert upper[-1] > ma[-1] > lower[-1]

    def test_kdj(self):
        from src.strategies.base import kdj
        highs = [55 + i * 0.1 for i in range(30)]
        lows = [45 + i * 0.1 for i in range(30)]
        closes = [50 + i * 0.1 for i in range(30)]
        k, d, j = kdj(highs, lows, closes)
        assert k[-1] is not None
        assert d[-1] is not None
        assert j[-1] is not None


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------

class TestMACrossStrategy:
    def test_params(self):
        from src.strategies.builtin import MACrossStrategy
        s = MACrossStrategy()
        assert s.get_params() == {"fast": 5, "slow": 20, "stop_loss_pct": 5.0}

    def test_custom_params(self):
        from src.strategies.builtin import MACrossStrategy
        s = MACrossStrategy(fast=8, slow=30, stop_loss_pct=3.0)
        assert s.params["fast"] == 8
        assert s.params["slow"] == 30

    def test_generates_trades(self, mock_data):
        from src.strategies.builtin import MACrossStrategy
        s = MACrossStrategy()
        trades = s.generate_trades(mock_data)
        assert len(trades) > 0
        assert trades[0]["action"] == "buy"
        assert "price" in trades[0]

    def test_backtest_integration(self, mock_data):
        from src.strategies.builtin import MACrossStrategy
        from src.backtester import backtest
        s = MACrossStrategy()
        result = backtest(mock_data, 100000, s)
        assert result.num_trades >= 0
        assert result.total_return is not None
        assert result.sharpe_ratio is not None


class TestRSIStrategy:
    def test_bullish_not_triggered(self, trending_up_data):
        from src.strategies.builtin import RSIStrategy
        s = RSIStrategy()
        # In uptrend, RSI should be high → no oversold signal
        trades = s.generate_trades(trending_up_data)
        for t in trades:
            if t["action"] == "buy":
                # Should only buy when oversold
                assert "超卖" in t.get("reason", "")

    def test_params(self):
        from src.strategies.builtin import RSIStrategy
        s = RSIStrategy(period=10, oversold=25, overbought=75)
        assert s.params["period"] == 10


class TestMACDStrategy:
    def test_generates_trades(self, mock_data):
        from src.strategies.builtin import MACDStrategy
        s = MACDStrategy()
        trades = s.generate_trades(mock_data)
        # MACD may or may not generate signals on random data
        assert isinstance(trades, list)

    def test_below_zero_mode(self, mock_data):
        from src.strategies.builtin import MACDStrategy
        s = MACDStrategy(require_below_zero=True)
        trades = s.generate_trades(mock_data)
        assert isinstance(trades, list)


class TestBollingerStrategy:
    def test_generates_trades(self, mock_data):
        from src.strategies.builtin import BollingerStrategy
        s = BollingerStrategy()
        trades = s.generate_trades(mock_data)
        assert isinstance(trades, list)


class TestKDJStrategy:
    def test_generates_trades(self, mock_data):
        from src.strategies.builtin import KDJStrategy
        s = KDJStrategy()
        trades = s.generate_trades(mock_data)
        assert isinstance(trades, list)


class TestVolumeBreakStrategy:
    def test_no_break_on_low_volume(self, mock_data):
        from src.strategies.builtin import VolumeBreakStrategy
        s = VolumeBreakStrategy(vol_mult=10.0)  # Very high threshold
        trades = s.generate_trades(mock_data)
        # Should have very few or no trades
        buy_count = sum(1 for t in trades if t["action"] == "buy")
        assert buy_count <= 2


class TestTrendFollowStrategy:
    def test_alignment_detection(self, trending_up_data):
        from src.strategies.builtin import TrendFollowStrategy
        s = TrendFollowStrategy()
        trades = s.generate_trades(trending_up_data)
        assert isinstance(trades, list)

    def test_params_long_period(self):
        from src.strategies.builtin import TrendFollowStrategy
        s = TrendFollowStrategy(long=100)
        assert s._min_data_length() == 101


class TestMeanRevertStrategy:
    def test_reversion_detection(self, mock_data):
        from src.strategies.builtin import MeanRevertStrategy
        s = MeanRevertStrategy(deviation_pct=2.0)  # Sensitive threshold
        trades = s.generate_trades(mock_data)
        assert isinstance(trades, list)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestStrategyRegistry:
    def test_get_python_strategy(self):
        from src.strategies import get_python_strategy
        s = get_python_strategy("ma_cross")
        assert s is not None
        assert s.name == "ma_cross"

    def test_get_nonexistent(self):
        from src.strategies import get_python_strategy
        s = get_python_strategy("nonexistent")
        assert s is None

    def test_list_strategies(self):
        from src.strategies import list_strategies
        strats = list_strategies()
        assert len(strats) > 0

    def test_all_builtins_registered(self):
        from src.strategies import get_strategy_registry
        registry = get_strategy_registry()
        for name in ["ma_cross", "rsi_strategy", "macd_strategy", "bollinger",
                      "kdj_strategy", "volume_break", "trend_follow", "mean_revert"]:
            assert name in registry, f"{name} not in registry"


# ---------------------------------------------------------------------------
# Backtester compatibility
# ---------------------------------------------------------------------------

class TestBacktesterCompatibility:
    def test_backtest_with_strategy_instance(self, mock_data):
        from src.backtester import backtest, ma_crossover_strategy
        from src.strategies.builtin import MACrossStrategy

        # Old-style (callable)
        r1 = backtest(mock_data, 100000, ma_crossover_strategy)

        # New-style (BaseStrategy)
        r2 = backtest(mock_data, 100000, MACrossStrategy())

        assert r1.total_return is not None
        assert r2.total_return is not None

    def test_backtest_with_none(self):
        from src.backtester import backtest
        r = backtest([], 100000, None)
        assert r.num_trades == 0
        assert r.total_return == 0.0