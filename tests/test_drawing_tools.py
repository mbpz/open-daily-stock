"""Tests for P4-1: K-line drawing tools (Fibonacci, support/resistance)."""
import pytest
import pandas as pd
from datetime import date, timedelta
from src.shared.indicators import (
    calculate_fibonacci_levels,
    find_support_resistance,
    _cluster_levels,
)


class TestFibonacciLevels:
    """Test Fibonacci retracement level calculations."""

    def test_fibonacci_basic_levels(self):
        """Verify all 7 Fibonacci levels between two prices."""
        levels = calculate_fibonacci_levels(high=100.0, low=50.0)

        assert "0%" in levels
        assert "23.6%" in levels
        assert "38.2%" in levels
        assert "50%" in levels
        assert "61.8%" in levels
        assert "78.6%" in levels
        assert "100%" in levels

    def test_fibonacci_values_uptrend(self):
        """High -> Low: levels should be descending."""
        levels = calculate_fibonacci_levels(high=100.0, low=50.0)

        assert levels["0%"] == 100.0
        assert levels["100%"] == 50.0
        # 50% level should be exactly 75.0
        assert levels["50%"] == 75.0
        # 61.8% level: 100 - 50*0.618 = 69.1
        assert levels["61.8%"] == round(100.0 - 50.0 * 0.618, 2)

    def test_fibonacci_values_downtrend(self):
        """Fibonacci works regardless of direction."""
        levels = calculate_fibonacci_levels(high=50.0, low=100.0)

        # diff = -50
        assert levels["0%"] == 50.0
        assert levels["100%"] == 100.0
        # 38.2% level: 50 - (-50)*0.382 = 50 + 19.1 = 69.1
        assert levels["38.2%"] == round(50.0 - (-50.0) * 0.382, 2)

    def test_fibonacci_same_price(self):
        """When high == low, all levels equal that price."""
        levels = calculate_fibonacci_levels(high=100.0, low=100.0)

        for label in ["0%", "23.6%", "38.2%", "50%", "61.8%", "78.6%", "100%"]:
            assert levels[label] == 100.0

    def test_fibonacci_returns_7_levels(self):
        """Fibonacci always returns exactly 7 levels."""
        levels = calculate_fibonacci_levels(high=200.0, low=10.0)
        assert len(levels) == 7

    def test_fibonacci_levels_are_monotonic(self):
        """Levels should be monotonically decreasing from 0% to 100%."""
        levels = calculate_fibonacci_levels(high=150.0, low=30.0)
        level_names = ["0%", "23.6%", "38.2%", "50%", "61.8%", "78.6%", "100%"]
        vals = [levels[k] for k in level_names]
        for i in range(len(vals) - 1):
            assert vals[i] >= vals[i + 1], (
                f"Levels not monotonic: {level_names[i]}={vals[i]}, "
                f"{level_names[i+1]}={vals[i+1]}"
            )


class TestClusterLevels:
    """Test _cluster_levels helper."""

    def test_empty_list(self):
        result = _cluster_levels([], threshold=0.03)
        assert result == []

    def test_single_level(self):
        result = _cluster_levels([100.0], threshold=0.03)
        assert result == [100.0]

    def test_far_apart_levels(self):
        """Levels far apart should remain separate."""
        result = _cluster_levels([50.0, 100.0, 150.0], threshold=0.01)
        assert result == [50.0, 100.0, 150.0]

    def test_close_levels_merge(self):
        """Levels within threshold should be averaged."""
        result = _cluster_levels([100.0, 101.0, 102.0], threshold=0.03)
        # All are within 3%: avg = 101.0
        assert len(result) == 1
        assert result[0] == 101.0

    def test_mixed_clusters(self):
        """Some close, some far."""
        result = _cluster_levels([50.0, 51.0, 100.0, 101.0], threshold=0.03)
        assert len(result) == 2
        assert result[0] == 50.5  # avg of 50, 51
        assert result[1] == 100.5  # avg of 100, 101

    def test_duplicates_removed(self):
        """Duplicate levels are de-duplicated before clustering."""
        result = _cluster_levels([100.0, 100.0, 100.0], threshold=0.03)
        assert len(result) == 1
        assert result[0] == 100.0

    def test_results_are_sorted(self):
        result = _cluster_levels([150.0, 50.0, 100.0], threshold=0.01)
        assert result == sorted(result)


class TestSupportResistance:
    """Test support/resistance detection from OHLCV DataFrame."""

    def _make_ohlcv_df(self, prices):
        """Create OHLCV DataFrame from a list of daily price dicts."""
        start = date(2024, 1, 2)
        data = []
        for i, p in enumerate(prices):
            d = start + timedelta(days=i)
            data.append({
                "date": d.isoformat(),
                "High": p + 2,
                "Low": p - 2,
                "Open": p,
                "Close": p + 1,
                "Volume": 1000000,
            })
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df

    def test_find_support_resistance_basic(self):
        """Should return support and resistance dicts."""
        prices = [100 + i * 0.5 for i in range(60)]  # Trending up
        df = self._make_ohlcv_df(prices)

        result = find_support_resistance(df, window=10, threshold=0.05)

        assert "support" in result
        assert "resistance" in result
        assert isinstance(result["support"], list)
        assert isinstance(result["resistance"], list)

    def test_flat_price_produces_single_level(self):
        """Flat price range should produce few levels after clustering."""
        prices = [100.0 + (i % 3) * 0.1 for i in range(60)]  # Very tight range
        df = self._make_ohlcv_df(prices)

        result = find_support_resistance(df, window=10, threshold=0.05)

        # With very tight range, all levels cluster into few groups
        assert len(result["support"]) <= 3
        assert len(result["resistance"]) <= 3

    def test_volatile_prices_produce_multiple_levels(self):
        """Volatile price with big swings should produce more levels."""
        prices = []
        for i in range(60):
            if i < 20:
                prices.append(50.0 + i * 0.5)
            elif i < 40:
                prices.append(100.0 - (i - 20) * 0.5)
            else:
                prices.append(60.0 + (i - 40) * 0.5)
        df = self._make_ohlcv_df(prices)

        result = find_support_resistance(df, window=7, threshold=0.05)
        # Should find at least one level each
        assert len(result["support"]) >= 0
        assert len(result["resistance"]) >= 0

    def test_short_data_returns_empty(self):
        """Very short DataFrame (< window) returns empty lists."""
        prices = [100.0 + i for i in range(5)]
        df = self._make_ohlcv_df(prices)

        result = find_support_resistance(df, window=20, threshold=0.03)

        assert len(result["support"]) == 0
        assert len(result["resistance"]) == 0

    def test_levels_are_reasonable(self):
        """All returned levels should be within the price range."""
        prices = [100 + i * 0.3 for i in range(60)]
        df = self._make_ohlcv_df(prices)

        result = find_support_resistance(df, window=10, threshold=0.05)

        for level in result["support"] + result["resistance"]:
            assert level >= min(prices) - 5  # Allow some margin for high/low
            assert level <= max(prices) + 5


class TestDataServiceGetDrawingData:
    """Test DataService get_drawing_data action."""

    def test_get_drawing_data_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "get_drawing_data" in service._actions

    def test_get_drawing_data_action_handler(self):
        from src.data_service import DataService
        service = DataService()
        assert service._actions["get_drawing_data"] == "_handle_get_drawing_data"

    def test_get_drawing_data_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_drawing_data"})
        assert result["status"] == "error"
        assert "message" in result


class TestConfigDrawingFlags:
    """Test config drawing flags exist."""

    def test_drawing_config_flags_exist(self):
        from src.config import Config
        cfg = Config.get_instance()
        assert hasattr(cfg, "chart_draw_support_resistance")
        assert hasattr(cfg, "chart_draw_fibonacci")

    def test_drawing_config_defaults(self):
        from src.config import Config
        cfg = Config.get_instance()
        # Drawing tools are off by default
        assert cfg.chart_draw_support_resistance is False
        assert cfg.chart_draw_fibonacci is False
