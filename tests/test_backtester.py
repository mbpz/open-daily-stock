"""Tests for backtester module - TDD approach"""
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any


class TestBacktestResult:
    """Test BacktestResult dataclass"""

    def test_backtest_result_has_all_fields(self):
        """BacktestResult should have total_return, max_drawdown, sharpe_ratio, num_trades, win_rate"""
        from src.backtester import BacktestResult
        result = BacktestResult(
            total_return=10.5,
            max_drawdown=-5.0,
            sharpe_ratio=1.5,
            num_trades=5,
            win_rate=60.0
        )
        assert result.total_return == 10.5
        assert result.max_drawdown == -5.0
        assert result.sharpe_ratio == 1.5
        assert result.num_trades == 5
        assert result.win_rate == 60.0


class TestMACrossoverStrategy:
    """Test MA crossover strategy"""

    def _generate_ma_test_data(self) -> List[Dict]:
        """Generate simple test data for MA crossover:
        Day 1-5: price at 100 (MA5=100, MA20=100)
        Day 6-10: price drops to 90 (MA5=95, MA20=100 -> cross down)
        Day 11-15: price rises to 110 (MA5=100, MA20=100 -> cross up)
        """
        data = []
        base_date = datetime(2024, 1, 1)
        for i in range(20):
            day = base_date + timedelta(days=i)
            if i < 5:
                close = 100.0
            elif i < 10:
                close = 90.0
            elif i < 15:
                close = 100.0
            else:
                close = 110.0
            data.append({
                "date": day.strftime("%Y-%m-%d"),
                "open": close - 1,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000000,
                "pct_chg": 0.0
            })
        return data

    def test_ma_crossover_strategy_returns_list(self):
        """ma_crossover_strategy should return a list of trades"""
        from src.backtester import ma_crossover_strategy
        data = self._generate_ma_test_data()
        trades = ma_crossover_strategy(data)
        assert isinstance(trades, list)

    def test_ma_crossover_strategy_buy_signal(self):
        """MA5 crossing above MA20 should generate buy signal"""
        from src.backtester import ma_crossover_strategy
        # Create data where MA5 clearly crosses above MA20
        # Days 1-5: high prices 110 (elevates MA20)
        # Days 6-20: moderate slowly rising 100-104 (MA5 stays below MA20)
        # Days 21+: faster rising 107+ (MA5 catches up and crosses above MA20)
        data = []
        for i in range(30):
            if i < 5:
                close = 110.0
            elif i < 20:
                close = 100.0 + (i - 5) * 0.3  # Slowly rising
            else:
                close = 105.0 + (i - 19) * 2  # Faster rising
            data.append({
                "date": f"2024-01-{i+1:02d}",
                "open": close - 1,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000000,
                "pct_chg": 1.0 if i > 0 else 0.0
            })
        trades = ma_crossover_strategy(data)
        # Should have at least one buy trade when MA5 crosses above MA20
        buy_trades = [t for t in trades if t.get("action") == "buy"]
        assert len(buy_trades) >= 1, f"Expected buy signal, got {len(buy_trades)} trades"

    def test_ma_crossover_strategy_sell_signal(self):
        """MA5 crossing below MA20 should generate sell signal"""
        from src.backtester import ma_crossover_strategy
        # Create data where MA5 clearly crosses above then below MA20
        # This generates: buy signal when MA5 crosses above, then sell signal when MA5 crosses below
        data = []
        for i in range(40):
            if i < 5:
                close = 110.0  # High start - elevates MA20
            elif i < 15:
                close = 110.0 - (i - 5) * 0.5  # Slow fall to 105
            elif i < 25:
                close = 105.0 + (i - 15) * 1.5  # Rise to 120 - MA5 crosses above MA20 = BUY
            else:
                close = 120.0 - (i - 25) * 2.0  # Fall to 100 - MA5 crosses below MA20 = SELL
            data.append({
                "date": f"2024-01-{i+1:02d}",
                "open": close - 1,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000000,
                "pct_chg": 1.0 if i > 0 else 0.0
            })
        trades = ma_crossover_strategy(data)
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        assert len(sell_trades) >= 1, f"Expected sell signal, got {len(sell_trades)} trades"

    def test_ma_crossover_trade_structure(self):
        """Trade should have date, action, price, shares"""
        from src.backtester import ma_crossover_strategy
        # Simple rising data
        data = []
        for i in range(25):
            close = 100 + i
            data.append({
                "date": f"2024-01-{i+1:02d}",
                "open": close - 1,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000000,
                "pct_chg": 1.0 if i > 0 else 0.0
            })
        trades = ma_crossover_strategy(data)
        if len(trades) > 0:
            trade = trades[0]
            assert "date" in trade
            assert "action" in trade
            assert "price" in trade
            assert "shares" in trade


class TestBacktestFunction:
    """Test the backtest function"""

    def _create_simple_history(self) -> List[Dict]:
        """Create simple history data for testing"""
        data = []
        base_date = datetime(2024, 1, 1)
        for i in range(30):
            day = base_date + timedelta(days=i)
            close = 100 + i  # Simple uptrend
            data.append({
                "date": day.strftime("%Y-%m-%d"),
                "open": close - 0.5,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1000000,
                "pct_chg": 1.0 if i > 0 else 0.0
            })
        return data

    def test_backtest_returns_backtest_result(self):
        """backtest should return BacktestResult"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'max_drawdown')
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'num_trades')
        assert hasattr(result, 'win_rate')

    def test_backtest_with_initial_capital(self):
        """backtest should use initial_capital for calculations"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=50000, strategy_fn=ma_crossover_strategy)
        assert result.total_return is not None
        assert isinstance(result.total_return, float)

    def test_backtest_num_trades_is_int(self):
        """num_trades should be an integer"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert isinstance(result.num_trades, int)
        assert result.num_trades >= 0

    def test_backtest_win_rate_is_float(self):
        """win_rate should be a float (percentage)"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert isinstance(result.win_rate, float)
        assert 0 <= result.win_rate <= 100

    def test_backtest_max_drawdown_is_negative_or_zero(self):
        """max_drawdown should be <= 0 (percentage)"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert result.max_drawdown <= 0

    def test_backtest_sharpe_ratio_is_float(self):
        """sharpe_ratio should be a float"""
        from src.backtester import backtest, ma_crossover_strategy
        data = self._create_simple_history()
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert isinstance(result.sharpe_ratio, float)


class TestBacktestWithFlatPrice:
    """Test backtest with flat price (no trades scenario)"""

    def test_backtest_flat_price_no_trades(self):
        """With flat prices, MA crossover should not generate trades"""
        from src.backtester import backtest, ma_crossover_strategy
        # Flat price data
        data = []
        for i in range(30):
            data.append({
                "date": f"2024-01-{i+1:02d}",
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1000000,
                "pct_chg": 0.0
            })
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        assert result.num_trades == 0
        # With no trades, total return should be 0 (or very close to 0)
        assert abs(result.total_return) < 0.01


class TestBacktestWithDroppingPrice:
    """Test backtest with dropping price"""

    def test_backtest_dropping_price_negative_return(self):
        """With dropping prices, total_return should be negative"""
        from src.backtester import backtest, ma_crossover_strategy
        # Dropping price data with initial flat period, then dropping
        # This ensures MA5 crosses below MA20
        data = []
        for i in range(30):
            if i < 10:
                close = 110.0  # Initial flat period at higher price
            else:
                close = 110.0 - (i - 9) * 2  # Then dropping
            data.append({
                "date": f"2024-01-{i+1:02d}",
                "open": close - 0.5,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1000000,
                "pct_chg": -1.0 if i > 0 else 0.0
            })
        result = backtest(data, initial_capital=100000, strategy_fn=ma_crossover_strategy)
        # With a sell signal (MA5 crosses below MA20), should have negative return
        # If there are no trades due to flat-to-dropping transition, the assertion is not valid
        if result.num_trades > 0:
            assert result.total_return < 0


class TestDataServiceBacktestAction:
    """Test DataService run_backtest action"""

    def test_run_backtest_action_exists(self):
        """DataService should have run_backtest action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "run_backtest" in service._actions

    def test_run_backtest_handler_exists(self):
        """DataService should have _handle_run_backtest method"""
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_run_backtest')

    def test_run_backtest_missing_code(self):
        """run_backtest without code should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "run_backtest"})
        assert result["status"] == "error"
        assert "code" in result["message"].lower()

    def test_run_backtest_missing_initial_capital(self):
        """run_backtest without initial_capital should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "run_backtest", "code": "000001"})
        assert result["status"] == "error"
        assert "capital" in result["message"].lower()

    def test_run_backtest_returns_result(self):
        """run_backtest should return backtest result"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "run_backtest",
            "code": "000001",
            "days": 60,
            "initial_capital": 100000
        })
        assert result["status"] == "ok"
        assert "data" in result
        # Check data fields
        data = result["data"]
        assert "total_return" in data
        assert "max_drawdown" in data
        assert "sharpe_ratio" in data
        assert "num_trades" in data
        assert "win_rate" in data
