"""Tests for portfolio module (TDD - tests first)"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch


class TestPositionDataclass:
    """Test Position dataclass"""

    def test_position_creation(self):
        from src.portfolio import Position
        pos = Position(
            code="600519",
            name="贵州茅台",
            shares=100,
            buy_price=1500.0,
            buy_date=date(2024, 1, 15)
        )
        assert pos.code == "600519"
        assert pos.name == "贵州茅台"
        assert pos.shares == 100
        assert pos.buy_price == 1500.0
        assert pos.buy_date == date(2024, 1, 15)

    def test_position_with_current_price(self):
        from src.portfolio import Position
        pos = Position(
            code="600519",
            name="贵州茅台",
            shares=100,
            buy_price=1500.0,
            buy_date=date(2024, 1, 15)
        )
        # cost_basis = shares * buy_price = 100 * 1500 = 150000
        assert pos.cost_basis == 150000.0
        # current_value with default current_price = buy_price
        assert pos.current_value == 150000.0
        # unrealized_pnl = 0 when current_price == buy_price
        assert pos.unrealized_pnl == 0.0
        # return_pct = 0 when no change
        assert pos.return_pct == 0.0

    def test_position_profitable(self):
        from src.portfolio import Position
        pos = Position(
            code="600519",
            name="贵州茅台",
            shares=100,
            buy_price=1500.0,
            buy_date=date(2024, 1, 15)
        )
        # Set current price higher
        pos.current_price = 1800.0
        # current_value = 100 * 1800 = 180000
        assert pos.current_value == 180000.0
        # unrealized_pnl = 180000 - 150000 = 30000
        assert pos.unrealized_pnl == 30000.0
        # return_pct = 30000 / 150000 * 100 = 20%
        assert pos.return_pct == 20.0

    def test_position_losing(self):
        from src.portfolio import Position
        pos = Position(
            code="600519",
            name="贵州茅台",
            shares=100,
            buy_price=1500.0,
            buy_date=date(2024, 1, 15)
        )
        # Set current price lower
        pos.current_price = 1200.0
        # unrealized_pnl = 120000 - 150000 = -30000
        assert pos.unrealized_pnl == -30000.0
        # return_pct = -30000 / 150000 * 100 = -20%
        assert pos.return_pct == -20.0


class TestPositionCalculations:
    """Test Position calculation properties"""

    def test_cost_basis_calculation(self):
        from src.portfolio import Position
        pos = Position(
            code="000001",
            name="平安银行",
            shares=1000,
            buy_price=12.50,
            buy_date=date(2024, 3, 1)
        )
        # cost_basis = 1000 * 12.50 = 12500
        assert pos.cost_basis == 12500.0

    def test_current_value_with_price(self):
        from src.portfolio import Position
        pos = Position(
            code="000001",
            name="平安银行",
            shares=1000,
            buy_price=12.50,
            buy_date=date(2024, 3, 1)
        )
        pos.current_price = 13.75
        # current_value = 1000 * 13.75 = 13750
        assert pos.current_value == 13750.0

    def test_return_percentage_profit(self):
        from src.portfolio import Position
        pos = Position(
            code="000001",
            name="平安银行",
            shares=100,
            buy_price=10.0,
            buy_date=date(2024, 1, 1)
        )
        pos.current_price = 12.0
        # return_pct = (12 - 10) / 10 * 100 = 20%
        assert pos.return_pct == 20.0

    def test_return_percentage_loss(self):
        from src.portfolio import Position
        pos = Position(
            code="000001",
            name="平安银行",
            shares=100,
            buy_price=10.0,
            buy_date=date(2024, 1, 1)
        )
        pos.current_price = 8.0
        # return_pct = (8 - 10) / 10 * 100 = -20%
        assert pos.return_pct == -20.0


class TestDataServicePositionActions:
    """Test DataService position actions"""

    def test_add_position_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "_handle_add_position" in service._actions.values()

    def test_remove_position_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "_handle_remove_position" in service._actions.values()

    def test_update_position_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "_handle_update_position" in service._actions.values()

    def test_get_positions_action_exists(self):
        from src.data_service import DataService
        service = DataService()
        assert "_handle_get_positions" in service._actions.values()

    def test_add_position_success(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        assert result["status"] == "ok"
        assert "position" in result

    def test_add_position_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "add_position",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        assert result["status"] == "error"
        assert "code" in result["message"].lower()

    def test_add_position_missing_shares(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        assert result["status"] == "error"
        assert "shares" in result["message"].lower()

    def test_add_position_missing_buy_price(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_date": "2024-01-15"
        })
        assert result["status"] == "error"
        assert "buy_price" in result["message"].lower()

    def test_get_positions_empty(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_positions"})
        assert result["status"] == "ok"
        assert "positions" in result
        assert isinstance(result["positions"], list)

    def test_get_positions_after_adding(self):
        from src.data_service import DataService
        service = DataService()
        # Add a position first
        service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        # Get positions
        result = service._handle_request({"action": "get_positions"})
        assert result["status"] == "ok"
        assert len(result["positions"]) >= 1
        # Check position data structure
        pos = result["positions"][0]
        assert "code" in pos
        assert "name" in pos
        assert "shares" in pos
        assert "buy_price" in pos
        assert "buy_date" in pos

    def test_remove_position_success(self):
        from src.data_service import DataService
        service = DataService()
        # Add a position first
        add_result = service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        position_id = add_result["position"]["id"]
        # Remove it
        result = service._handle_request({
            "action": "remove_position",
            "id": position_id
        })
        assert result["status"] == "ok"

    def test_remove_position_not_found(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "remove_position",
            "id": 99999
        })
        assert result["status"] == "error"

    def test_update_position_success(self):
        from src.data_service import DataService
        service = DataService()
        # Add a position first
        add_result = service._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        position_id = add_result["position"]["id"]
        # Update it
        result = service._handle_request({
            "action": "update_position",
            "id": position_id,
            "current_price": 1600.0
        })
        assert result["status"] == "ok"
        assert result["position"]["current_price"] == 1600.0

    def test_update_position_not_found(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "update_position",
            "id": 99999,
            "current_price": 1600.0
        })
        assert result["status"] == "error"


class TestPositionPersistence:
    """Test positions table persistence"""

    def test_positions_table_exists(self):
        from src.data_service import DataService
        from src.storage import get_db
        import sqlite3
        service = DataService()
        db = get_db()
        db_path = db._engine.url.database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='positions'")
        result = c.fetchone()
        conn.close()
        assert result is not None, "positions table should exist"

    def test_position_persists_across_service_instances(self):
        from src.data_service import DataService
        import sqlite3
        # First service instance - add position
        service1 = DataService()
        service1._handle_request({
            "action": "add_position",
            "code": "600519",
            "name": "贵州茅台",
            "shares": 100,
            "buy_price": 1500.0,
            "buy_date": "2024-01-15"
        })
        # Second service instance - get positions should see it
        service2 = DataService()
        result = service2._handle_request({"action": "get_positions"})
        assert result["status"] == "ok"
        codes = [p["code"] for p in result["positions"]]
        assert "600519" in codes