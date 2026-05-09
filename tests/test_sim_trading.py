"""Tests for simulated trading (P4-2)."""
import pytest
from src.sim_trading import SimAccount, SimPosition, INITIAL_CAPITAL


class TestSimPosition:
    """Unit tests for SimPosition dataclass."""

    def test_cost_calculation(self):
        pos = SimPosition(code="000001", name="平安银行", shares=100,
                          buy_price=10.0, buy_date="2025-01-01")
        assert pos.cost == 1000.0

    def test_market_value_calculation(self):
        pos = SimPosition(code="000001", name="平安银行", shares=100,
                          buy_price=10.0, buy_date="2025-01-01",
                          current_price=12.0)
        assert pos.market_value == 1200.0

    def test_pnl_positive(self):
        pos = SimPosition(code="000001", name="平安银行", shares=100,
                          buy_price=10.0, buy_date="2025-01-01",
                          current_price=12.0)
        assert pos.pnl == 200.0
        assert pos.pnl_pct == 20.0

    def test_pnl_negative(self):
        pos = SimPosition(code="000001", name="平安银行", shares=100,
                          buy_price=10.0, buy_date="2025-01-01",
                          current_price=8.0)
        assert pos.pnl == -200.0
        assert pos.pnl_pct == -20.0

    def test_pnl_pct_zero_cost(self):
        pos = SimPosition(code="000001", name="平安银行", shares=0,
                          buy_price=0.0, buy_date="2025-01-01")
        assert pos.pnl_pct == 0.0

    def test_to_dict(self):
        pos = SimPosition(code="000001", name="平安银行", shares=100,
                          buy_price=10.0, buy_date="2025-01-01",
                          current_price=12.0)
        d = pos.to_dict()
        assert d["code"] == "000001"
        assert d["shares"] == 100
        assert d["pnl"] == 200.0

    def test_from_dict(self):
        d = {"code": "000001", "name": "平安银行", "shares": 100,
             "buy_price": 10.0, "buy_date": "2025-01-01",
             "current_price": 12.0}
        pos = SimPosition.from_dict(d)
        assert pos.code == "000001"
        assert pos.shares == 100
        assert pos.current_price == 12.0


class TestSimAccount:
    """Unit tests for SimAccount."""

    def test_initial_state(self):
        account = SimAccount()
        assert account.cash == INITIAL_CAPITAL
        assert account.total_assets == INITIAL_CAPITAL
        assert account.total_pnl == 0.0
        assert account.total_pnl_pct == 0.0
        assert len(account.positions) == 0
        assert len(account.trade_history) == 0

    def test_buy_reduces_cash(self):
        account = SimAccount()
        result = account.buy("000001", "平安银行", 10.0, 100)
        assert result["status"] == "ok"
        # cost: 1000 + commission: max(1000*0.00025, 5) = 5.0 -> total 1005
        assert account.cash == INITIAL_CAPITAL - 1005.0
        assert "000001" in account.positions
        assert account.positions["000001"].shares == 100
        assert len(account.trade_history) == 1

    def test_sell_increases_cash(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        cash_before = account.cash
        result = account.sell("000001", 12.0, 100)
        assert result["status"] == "ok"
        # revenue: 1200 - commission(5) - stamp(1.2) = 1193.8
        assert account.cash == cash_before + 1193.8
        assert "000001" not in account.positions
        assert len(account.trade_history) == 2

    def test_sell_partial(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 50)
        result = account.sell("000001", 12.0, 30)
        assert result["status"] == "ok"
        assert account.positions["000001"].shares == 20

    def test_sell_all_default(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 50)
        result = account.sell("000001", 12.0)  # shares=None -> sell all
        assert result["status"] == "ok"
        assert "000001" not in account.positions

    def test_insufficient_cash_returns_error(self):
        account = SimAccount()
        account.cash = 100.0  # force low cash
        result = account.buy("000001", "平安银行", 100.0, 100)  # needs ~10005
        assert result["status"] == "error"
        assert "资金不足" in result["message"]

    def test_sell_unowned_stock_returns_error(self):
        account = SimAccount()
        result = account.sell("000001", 10.0)
        assert result["status"] == "error"
        assert "未持有" in result["message"]

    def test_sell_more_than_owned_returns_error(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 50)
        result = account.sell("000001", 12.0, 100)  # try to sell 100, only have 50
        assert result["status"] == "error"
        assert "持仓不足" in result["message"]

    def test_update_prices(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        account.buy("600519", "贵州茅台", 1600.0, 100)
        account.update_prices({"000001": 12.0, "600519": 1700.0, "999999": 5.0})
        assert account.positions["000001"].current_price == 12.0
        assert account.positions["600519"].current_price == 1700.0

    def test_total_assets_with_positions(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)  # costs 1005
        account.update_prices({"000001": 12.0})
        # cash: 998995, market_value: 1200
        assert account.total_assets == account.cash + 1200.0

    def test_commission_tracking(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        # commission: max(1000*0.00025, 5.0) = 5.0
        assert account.total_commission == 5.0

    def test_reset(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        account = SimAccount()  # new account = reset
        assert account.cash == INITIAL_CAPITAL
        assert len(account.positions) == 0
        assert len(account.trade_history) == 0

    def test_average_price_on_second_buy(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)  # buy_price=10
        account.buy("000001", "平安银行", 20.0, 100)  # avg = (1000+2000)/200 = 15
        pos = account.positions["000001"]
        assert pos.shares == 200
        assert pos.buy_price == 15.0

    def test_get_summary(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        summary = account.get_summary()
        assert summary["position_count"] == 1
        assert "cash" in summary
        assert "total_assets" in summary
        assert "total_pnl" in summary
        assert "positions" in summary
        assert len(summary["positions"]) == 1

    def test_to_dict_and_from_dict_roundtrip(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        account.update_prices({"000001": 12.0})

        d = account.to_dict()
        restored = SimAccount.from_dict(d)

        assert restored.cash == account.cash
        assert restored.total_commission == account.total_commission
        assert len(restored.positions) == len(account.positions)
        assert restored.positions["000001"].shares == 100
        assert restored.positions["000001"].buy_price == 10.0
        assert len(restored.trade_history) == 1

    def test_trade_history_records_all_trades(self):
        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        account.buy("600519", "贵州茅台", 1600.0, 50)
        account.sell("000001", 12.0, 50)
        assert len(account.trade_history) == 3
        assert account.trade_history[0]["action"] == "buy"
        assert account.trade_history[2]["action"] == "sell"


class TestSimTradingStorage:
    """Tests for sim account persistence via storage.py."""

    def test_save_and_load_sim_account(self):
        from src.sim_trading import SimAccount
        from src.storage import DatabaseManager

        # Reset singleton to use in-memory DB for isolation
        DatabaseManager.reset_instance()
        db = DatabaseManager.get_instance()

        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)

        db.save_sim_account(account.to_dict())
        loaded = db.load_sim_account()

        assert loaded is not None
        assert loaded["cash"] == account.cash
        assert "000001" in loaded["positions"]
        assert len(loaded["trade_history"]) == 1

        # Clean up
        DatabaseManager.reset_instance()

    def test_save_none_clears_account(self):
        from src.sim_trading import SimAccount
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()
        db = DatabaseManager.get_instance()

        account = SimAccount()
        account.buy("000001", "平安银行", 10.0, 100)
        db.save_sim_account(account.to_dict())

        # Clear
        db.save_sim_account(None)
        loaded = db.load_sim_account()
        assert loaded is None

        DatabaseManager.reset_instance()

    def test_load_returns_none_when_no_data(self):
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()
        db = DatabaseManager.get_instance()

        loaded = db.load_sim_account()
        assert loaded is None

        DatabaseManager.reset_instance()
