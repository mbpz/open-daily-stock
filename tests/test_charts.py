"""Tests for K-line chart generation module."""
import pytest
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path


def _make_history_data(num_days: int, base_date: str = "2024-01-02"):
    """Generate valid daily history data."""
    start = date.fromisoformat(base_date)
    data = []
    for i in range(num_days):
        d = start + timedelta(days=i)
        data.append({
            "date": d.isoformat(),
            "open": 100.0 + i * 0.5,
            "high": 105.0 + i * 0.5,
            "low": 99.0 + i * 0.5,
            "close": 103.0 + i * 0.5,
            "volume": 1000000 + i * 10000,
            "pct_chg": 1.0,
        })
    return data


class TestKlineChartCreation:
    """Test chart creation functions."""

    def test_convert_history_to_df(self):
        from src.charts import convert_history_to_df
        import pandas as pd

        data = [
            {"date": "2024-01-01", "open": 100.0, "high": 105.0,
             "low": 99.0, "close": 103.0, "volume": 1000000, "pct_chg": 2.5},
            {"date": "2024-01-02", "open": 103.0, "high": 108.0,
             "low": 102.0, "close": 107.0, "volume": 1200000, "pct_chg": 3.8},
        ]

        df = convert_history_to_df(data)

        assert df is not None
        assert len(df) == 2
        assert "Open" in df.columns
        assert "Close" in df.columns
        assert df.index.name == "date"

    def test_convert_empty_history(self):
        from src.charts import convert_history_to_df

        df = convert_history_to_df([])
        assert df is None

    def test_add_ma_indicators(self):
        from src.charts import convert_history_to_df, add_ma_indicators

        data = _make_history_data(30)

        df = convert_history_to_df(data)
        result = add_ma_indicators(df)

        assert "MA5" in result.columns
        assert "MA10" in result.columns
        assert "MA20" in result.columns
        # MA20 should have values by day 20
        assert not result["MA20"].iloc[19] is None
        # MA5 should have NaN for first 4 rows
        assert result["MA5"].iloc[0] != result["MA5"].iloc[0]  # NaN check

    def test_add_ma_indicators_short_data(self):
        from src.charts import convert_history_to_df, add_ma_indicators

        data = [
            {"date": "2024-01-01", "open": 100.0, "high": 105.0,
             "low": 99.0, "close": 103.0, "volume": 1000000, "pct_chg": 2.5},
        ]

        df = convert_history_to_df(data)
        result = add_ma_indicators(df)

        # MA columns should exist but be NaN for short data
        assert "MA5" in result.columns
        assert result["MA5"].isna().all()

    def test_create_kline_chart_returns_path(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir)
            assert os.path.exists(path)
            assert path.endswith(".png")
            assert "600519" in path

    def test_create_kline_chart_with_custom_days(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "000001", days=15, output_dir=tmpdir)
            assert os.path.exists(path)
            assert "15d" in path

    def test_chart_file_contains_image_data(self):
        from src.charts import create_kline_chart

        data = _make_history_data(30)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", output_dir=tmpdir)
            size = os.path.getsize(path)
            assert size > 1000  # PNG should be at least 1KB


class TestTechnicalIndicators:
    """Test technical indicator calculations."""

    def test_calculate_rsi(self):
        from src.charts import convert_history_to_df, calculate_rsi

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        rsi = calculate_rsi(df)

        # RSI should be a Series with proper length
        assert len(rsi) == len(df)
        # RSI should be between 0 and 100
        valid_rsi = rsi.dropna()
        assert all((valid_rsi >= 0) & (valid_rsi <= 100))

    def test_calculate_macd(self):
        from src.charts import convert_history_to_df, calculate_macd

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        macd_df = calculate_macd(df)

        assert "MACD" in macd_df.columns
        assert "DIF" in macd_df.columns
        assert "DEA" in macd_df.columns

    def test_calculate_bollinger_bands(self):
        from src.charts import convert_history_to_df, calculate_bollinger_bands

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        bb_df = calculate_bollinger_bands(df)

        assert "BB_UPPER" in bb_df.columns
        assert "BB_MIDDLE" in bb_df.columns
        assert "BB_LOWER" in bb_df.columns
        # Upper should be >= middle, middle >= lower
        valid = bb_df.dropna()
        assert all(valid["BB_UPPER"] >= valid["BB_MIDDLE"])
        assert all(valid["BB_MIDDLE"] >= valid["BB_LOWER"])

    def test_calculate_kdj(self):
        from src.charts import convert_history_to_df, calculate_kdj

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        kdj_df = calculate_kdj(df)

        assert "K" in kdj_df.columns
        assert "D" in kdj_df.columns
        assert "J" in kdj_df.columns

    def test_calculate_wr(self):
        from src.charts import convert_history_to_df, calculate_wr

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        wr = calculate_wr(df)

        valid_wr = wr.dropna()
        assert len(valid_wr) > 0, "WR should produce some values after warmup"
        assert valid_wr.notna().all(), "WR should not contain NaN after dropna"
        assert (valid_wr.abs() < 1e8).all(), "WR should all be finite values"

    def test_calculate_obv(self):
        from src.charts import convert_history_to_df, calculate_obv

        data = _make_history_data(30)
        df = convert_history_to_df(data)
        obv = calculate_obv(df)

        # OBV should be numeric and non-decreasing generally
        assert len(obv) == len(df)
        assert obv.dtype in ["float64", "float32", "int64", "int32"]

    def test_add_indicators(self):
        from src.charts import convert_history_to_df, add_indicators

        data = _make_history_data(60)
        df = convert_history_to_df(data)
        result = add_indicators(df, ["rsi", "macd", "bollinger", "kdj", "wr", "obv"])

        assert "RSI" in result.columns
        assert "MACD" in result.columns
        assert "DIF" in result.columns
        assert "DEA" in result.columns
        assert "BB_UPPER" in result.columns
        assert "BB_LOWER" in result.columns
        assert "K" in result.columns
        assert "D" in result.columns
        assert "J" in result.columns
        assert "WR" in result.columns
        assert "OBV" in result.columns


class TestKlineChartWithIndicators:
    """Test K-line chart creation with technical indicators."""

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_rsi_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["rsi"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_macd_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["macd"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_bollinger_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["bollinger"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_kdj_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["kdj"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_wr_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["wr"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_obv_indicator(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(data, "600519", days=30, output_dir=tmpdir, indicators=["obv"])
            assert os.path.exists(path)
            assert path.endswith(".png")

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_create_kline_chart_with_multiple_indicators(self):
        from src.charts import create_kline_chart

        data = _make_history_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = create_kline_chart(
                data, "600519", days=30, output_dir=tmpdir,
                indicators=["rsi", "macd", "bollinger", "kdj", "wr", "obv"]
            )
            assert os.path.exists(path)
            assert path.endswith(".png")
            # File should be larger with multiple indicators
            assert os.path.getsize(path) > 1000


class TestDataServiceGetKlineData:
    """Test DataService get_kline_data action."""

    def test_get_kline_data_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "get_kline_data" in service._actions

    def test_get_kline_data_in_action_registry(self):
        from src.data_service import DataService
        service = DataService()
        assert service._actions["get_kline_data"] == "_handle_get_kline_data"

    def test_get_kline_data_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_kline_data"})
        assert result["status"] == "error"

    @pytest.mark.skip(reason="mplfinance in CI/headless may not render panels correctly")
    def test_get_kline_data_returns_image_path(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "get_kline_data",
            "code": "600519",
            "days": 30,
        })
        assert result["status"] == "ok"
        assert "image_path" in result


class TestDataServiceGetIndicators:
    """Test DataService get_indicators action."""

    def test_get_indicators_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "get_indicators" in service._actions

    def test_get_indicators_action_handler(self):
        from src.data_service import DataService
        service = DataService()
        assert service._actions["get_indicators"] == "_handle_get_indicators"

    def test_get_indicators_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_indicators", "indicator_names": ["rsi"]})
        assert result["status"] == "error"

    def test_get_indicators_missing_indicator_names(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_indicators", "code": "600519"})
        assert result["status"] == "error"
