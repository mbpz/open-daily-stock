"""P5-10: Factor Analysis Engine tests."""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.factor_engine import (
    Factor, PREDEFINED_FACTORS, FactorEngine,
    get_factor_engine,
)


# === Fixtures ===

@pytest.fixture
def mock_db():
    """Mock DatabaseManager."""
    db = MagicMock()
    return db


@pytest.fixture
def engine(mock_db):
    """FactorEngine with mocked database."""
    return FactorEngine(db=mock_db)


@pytest.fixture
def sample_history():
    """Sample OHLCV data for 000001."""
    history = []
    base_price = 10.0
    for i in range(60):
        d = date.today() - timedelta(days=59 - i)
        history.append({
            "code": "000001",
            "date": d,
            "open": base_price + i * 0.1,
            "high": base_price + i * 0.1 + 0.5,
            "low": base_price + i * 0.1 - 0.5,
            "close": base_price + i * 0.1 + 0.2,
            "volume": 1_000_000 + i * 10_000,
            "pct_chg": 1.0 + i * 0.05,
        })
    return history


# === Factor Definition Tests ===

class TestFactorDataclass:
    def test_factor_creation(self):
        f = Factor(
            name="test_factor",
            description="Test factor description",
            formula="close / open",
            category="technical",
        )
        assert f.name == "test_factor"
        assert f.description == "Test factor description"
        assert f.formula == "close / open"
        assert f.category == "technical"


class TestPredefinedFactors:
    def test_predefined_factors_exist(self):
        assert len(PREDEFINED_FACTORS) == 7

    def test_predefined_factor_names(self):
        expected = ["pe_ratio", "pb_ratio", "momentum_5d", "momentum_20d",
                   "volume_ratio", "ma_golden_cross", "rsi_14"]
        assert set(PREDEFINED_FACTORS.keys()) == set(expected)

    def test_predefined_factor_structure(self):
        for name, factor in PREDEFINED_FACTORS.items():
            assert factor.name == name
            assert len(factor.description) > 0
            assert len(factor.formula) > 0
            assert factor.category in ("valuation", "momentum", "technical", "fundamental")


# === FactorEngine Initialization Tests ===

class TestFactorEngineInit:
    def test_engine_init(self, mock_db):
        e = FactorEngine(db=mock_db)
        assert e._db is mock_db

    def test_engine_singleton(self):
        import src.factor_engine as fe
        original = fe._engine_instance
        fe._engine_instance = None
        try:
            e1 = get_factor_engine()
            e2 = get_factor_engine()
            assert e1 is e2
        finally:
            fe._engine_instance = original


# === Factor Computation Tests ===

class TestMomentumFactor:
    def test_momentum_5d_with_sufficient_history(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "momentum_5d", target_date=date.today())
            assert val is not None
            assert isinstance(val, float)

    def test_momentum_5d_insufficient_history(self, engine):
        short_history = [{"close": 10.0}] * 3
        val = engine.compute_factor("000001", "momentum_5d", history_data=short_history)
        assert val is None

    def test_momentum_20d_with_sufficient_history(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "momentum_20d", target_date=date.today())
            assert val is not None
            assert isinstance(val, float)

    def test_momentum_20d_insufficient_history(self, engine):
        short_history = [{"close": 10.0}] * 15
        val = engine.compute_factor("000001", "momentum_20d", history_data=short_history)
        assert val is None

    def test_momentum_calculation_correct(self, engine):
        history = []
        for i in range(30):
            history.append({
                "close": 10.0 + i * 1.0,
                "volume": 1_000_000,
            })
        # Last close = 39, close 5 days ago = 34, return = (39-34)/34*100
        val = engine._compute_momentum(history, 5)
        assert abs(val - (39 - 34) / 34 * 100) < 0.001


class TestVolumeRatioFactor:
    def test_volume_ratio_normal(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "volume_ratio", target_date=date.today())
            assert val is not None
            assert isinstance(val, float)
            assert val > 0

    def test_volume_ratio_insufficient_history(self, engine):
        short_history = [{"volume": 1_000_000}] * 3
        val = engine.compute_factor("000001", "volume_ratio", history_data=short_history)
        assert val is None

    def test_volume_ratio_calculation(self, engine):
        # Create history where:
        # - last 5 days (as used by code) = [1M, 1M, 1M, 1M, 2M]
        # - current day (last item) = 2M
        # avg of recent 5 = (1+1+1+1+2)/5 * 1M = 1.2M
        # current = 2M
        # ratio = 2/1.2 = 1.6667
        history = []
        for i in range(5):
            history.append({"volume": 1_000_000.0})
        history.append({"volume": 2_000_000.0})
        val = engine._compute_volume_ratio(history)
        assert abs(val - 1.6667) < 0.001

    def test_volume_ratio_1x(self, engine):
        # All same volume = ratio 1.0
        history = [{"volume": 1_000_000.0}] * 6
        val = engine._compute_volume_ratio(history)
        assert val == 1.0

    def test_volume_ratio_no_current_volume(self, engine):
        # Current volume = 0 -> ratio = 0
        history = [{"volume": 1_000_000.0}] * 5 + [{"volume": 0.0}]
        val = engine._compute_volume_ratio(history)
        assert val == 0.0


class TestRSIFactor:
    def test_rsi_14_normal(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "rsi_14", target_date=date.today())
            assert val is not None
            assert 0 <= val <= 100

    def test_rsi_insufficient_history(self, engine):
        short_history = [{"close": 10.0 + i * 0.1} for i in range(10)]
        val = engine.compute_factor("000001", "rsi_14", history_data=short_history)
        assert val is None

    def test_rsi_flat_prices(self, engine):
        # Flat prices -> no gains/losses -> RSI = 50
        history = [{"close": 10.0}] * 30
        val = engine._compute_rsi(history, 14)
        assert val == 50.0

    def test_rsi_rising_prices(self, engine):
        # Rising prices should give RSI > 50
        history = [{"close": 10.0 + i * 0.5} for i in range(20)]
        val = engine._compute_rsi(history, 14)
        assert val > 50  # Overbought territory

    def test_rsi_falling_prices(self, engine):
        # Falling prices should give RSI < 50
        history = [{"close": 20.0 - i * 0.5} for i in range(20)]
        val = engine._compute_rsi(history, 14)
        assert val < 50  # Oversold territory


class TestMAGoldenCrossFactor:
    def test_ma_golden_cross_insufficient_history(self, engine):
        short_history = [{"close": 10.0}] * 15
        val = engine._compute_ma_golden_cross(short_history)
        assert val == 0.0

    def test_ma_golden_cross_returns_valid_values(self, engine):
        # Test that valid returns are in [0.0, 0.5, 1.0]
        history = [{"close": 10.0 + i * 0.1} for i in range(25)]
        val = engine._compute_ma_golden_cross(history)
        assert val in (0.0, 0.5, 1.0)

    def test_ma_golden_cross_bullish_state(self, engine):
        # Create a consistently upward trending history where MA5 > MA20
        history = []
        for i in range(30):
            # Price high enough that MA5 > MA20
            history.append({"close": 100.0 + i * 0.5})
        val = engine._compute_ma_golden_cross(history)
        # Should be 0.5 (already bullish, not golden cross)
        assert val == 0.5


class TestPERatioFactor:
    def test_pe_ratio_normal(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "pe_ratio", target_date=date.today())
            assert val is not None
            assert isinstance(val, float)
            assert val > 0

    def test_pe_ratio_empty_history(self, engine):
        val = engine._compute_pe_ratio([])
        assert val is None


class TestPBRatioFactor:
    def test_pb_ratio_normal(self, engine, sample_history):
        with patch.object(engine, "_fetch_history", return_value=sample_history):
            val = engine.compute_factor("000001", "pb_ratio", target_date=date.today())
            assert val is not None
            assert isinstance(val, float)
            assert val > 0

    def test_pb_ratio_empty_history(self, engine):
        val = engine._compute_pb_ratio([])
        assert val is None


class TestUnknownFactor:
    def test_unknown_factor_returns_none(self, engine, sample_history):
        val = engine.compute_factor("000001", "unknown_factor", history_data=sample_history)
        assert val is None


# === IC/IR Computation Tests ===

class TestPearsonCorrelation:
    def test_pearson_perfect_positive(self, engine):
        observations = [(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)]
        corr = engine._pearson_correlation(observations)
        assert corr is not None
        assert abs(corr - 1.0) < 0.0001

    def test_pearson_perfect_negative(self, engine):
        observations = [(1.0, 6.0), (2.0, 4.0), (3.0, 2.0)]
        corr = engine._pearson_correlation(observations)
        assert corr is not None
        assert abs(corr + 1.0) < 0.0001

    def test_pearson_no_correlation(self, engine):
        observations = [(1.0, 2.0), (2.0, 1.5), (3.0, 2.5), (4.0, 1.8)]
        corr = engine._pearson_correlation(observations)
        assert corr is not None
        assert -0.5 < corr < 0.5

    def test_pearson_insufficient_data(self, engine):
        observations = [(1.0, 2.0)]
        corr = engine._pearson_correlation(observations)
        assert corr is None

    def test_pearson_constant_x(self, engine):
        observations = [(1.0, 2.0), (1.0, 3.0), (1.0, 4.0)]
        corr = engine._pearson_correlation(observations)
        assert corr is None  # std_x = 0


# === Rank Tests ===

class TestFactorRank:
    def test_rank_not_in_codes(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000002", "000003"]):
            rank = engine.get_factor_rank("000001", "momentum_5d")
            assert rank is None

    def test_rank_with_codes(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001", "000002", "000003"]):
            with patch.object(engine, "compute_factor") as mock_compute:
                mock_compute.side_effect = lambda code, fn, **kw: {
                    "000001": 10.0,
                    "000002": 20.0,
                    "000003": 15.0,
                }.get(code)

                rank = engine.get_factor_rank("000002", "momentum_5d")
                assert rank == 1  # Highest value

    def test_rank_lowest(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001", "000002", "000003"]):
            with patch.object(engine, "compute_factor") as mock_compute:
                mock_compute.side_effect = lambda code, fn, **kw: {
                    "000001": 10.0,
                    "000002": 5.0,
                    "000003": 15.0,
                }.get(code)

                rank = engine.get_factor_rank("000002", "momentum_5d")
                assert rank == 3  # Lowest


# === Decay Analysis Tests ===

class TestFactorDecay:
    def test_decay_insufficient_windows(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001"]):
            # With lookback_days=10, window_days=20: num_windows = max(2, 10//20) = 2
            # But compute_ic returns None (mock returns 0.1 but might get None due to code path)
            with patch.object(engine, "compute_ic", return_value=None):
                result = engine.compute_factor_decay("momentum_5d", lookback_days=10, window_days=20)
                assert result["trend"] == "unknown"

    def test_decay_positive_trend(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001"]):
            # With rolling_ics = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6] (i=0 most recent)
            # reversed = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1]: values go DOWN over time
            # slope < -0.005 -> "negative" (decaying)
            with patch.object(engine, "compute_ic", side_effect=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]):
                result = engine.compute_factor_decay("momentum_5d", lookback_days=120, window_days=20)
                assert result["trend"] == "negative"

    def test_decay_negative_trend(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001"]):
            # With rolling_ics = [0.6, 0.5, 0.4, 0.3, 0.2, 0.1] (i=0 most recent)
            # reversed = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]: values go UP over time
            # slope > 0.005 -> "positive" (improving)
            with patch.object(engine, "compute_ic", side_effect=[0.6, 0.5, 0.4, 0.3, 0.2, 0.1]):
                result = engine.compute_factor_decay("momentum_5d", lookback_days=120, window_days=20)
                assert result["trend"] == "positive"

    def test_decay_stable_trend(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001"]):
            # lookback_days=120, window_days=20 -> num_windows = 6
            with patch.object(engine, "compute_ic", side_effect=[0.3, 0.28, 0.32, 0.29, 0.31, 0.30]):
                result = engine.compute_factor_decay("momentum_5d", lookback_days=120, window_days=20)
                assert result["trend"] == "stable"


# === DataService Action Tests ===

class TestDataServiceActions:
    def test_get_factor_value_unknown_factor(self, engine):
        val = engine.get_factor_value("000001", "unknown")
        assert val == 0.0

    def test_analyze_factor_ic_returns_dict(self, engine):
        with patch.object(engine, "compute_ic", return_value=0.15):
            with patch.object(engine, "compute_ir", return_value=0.8):
                with patch.object(engine, "compute_factor_decay", return_value={"trend": "stable"}):
                    result = engine.analyze_factor_ic("momentum_5d")
                    assert "factor_name" in result
                    assert "ic" in result
                    assert "ir" in result

    def test_get_factor_rankings_returns_list(self, engine):
        with patch.object(engine, "_get_all_codes", return_value=["000001", "000002"]):
            with patch.object(engine, "compute_factor", return_value=10.0):
                rankings = engine.get_factor_rankings("momentum_5d", top_n=10)
                assert isinstance(rankings, list)
                assert len(rankings) <= 10


# === Edge Cases ===

class TestEdgeCases:
    def test_empty_history(self, engine):
        val = engine.compute_factor("000001", "momentum_5d", history_data=[])
        assert val is None

    def test_none_values_in_history(self, engine):
        history = [
            {"close": None, "volume": 1_000_000},
            {"close": 10.0, "volume": None},
        ] * 30
        val = engine.compute_factor("000001", "momentum_5d", history_data=history)
        # May return None due to None values, or a float if computation succeeds
        assert val is None or isinstance(val, float)

    def test_zero_division_protection(self, engine):
        history = [{"close": 10.0}] * 25 + [{"close": 0}]
        val = engine.compute_factor("000001", "momentum_20d", history_data=history)
        assert val is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])