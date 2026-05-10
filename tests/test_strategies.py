"""Tests for strategy import/export functionality - P4-5"""
import json
import os
import pytest
from pathlib import Path
from typing import Dict, Any


# Sample strategy JSON for testing
SAMPLE_STRATEGY = {
    "name": "MA Cross Strategy",
    "version": "1.0",
    "description": "Golden cross strategy using MA5/MA20",
    "author": "testuser",
    "params": {
        "fast_ma": 5,
        "slow_ma": 20,
        "initial_capital": 100000,
        "stop_loss_pct": -5.0,
    },
    "code": "python",
    "indicators": ["ma5", "ma20"],
    "entry_rule": "MA5 crosses above MA20",
    "exit_rule": "MA5 crosses below MA20",
}

SAMPLE_STRATEGY_JSON = json.dumps(SAMPLE_STRATEGY, ensure_ascii=False)

SAMPLE_STRATEGY_2 = {
    "name": "RSI Bollinger Combo",
    "version": "1.0",
    "description": "RSI + Bollinger Bands combo strategy",
    "author": "testuser2",
    "params": {
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bb_period": 20,
        "bb_std": 2,
        "initial_capital": 100000,
        "stop_loss_pct": -8.0,
    },
    "code": "python",
    "indicators": ["rsi", "bollinger_upper", "bollinger_lower"],
    "entry_rule": "RSI < 30 AND price <= Bollinger lower",
    "exit_rule": "RSI > 70 OR price >= Bollinger upper",
}


class TestStrategyExportAction:
    """Test export_strategy DataService action"""

    def test_export_strategy_action_exists(self):
        """DataService should have export_strategy action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "export_strategy" in service._actions

    def test_export_strategy_handler_exists(self):
        """DataService should have _handle_export_strategy method"""
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_export_strategy')

    def test_export_strategy_missing_name(self):
        """export_strategy without name should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "export_strategy"})
        assert result["status"] == "error"
        assert "name" in result["message"].lower()

    def test_export_strategy_success(self):
        """export_strategy with valid data should succeed"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "export_strategy",
            "name": "MA Cross Strategy",
            "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000},
            "entry_rule": "MA5 crosses above MA20",
            "exit_rule": "MA5 crosses below MA20",
        })
        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["name"] == "MA Cross Strategy"
        # Verify file was created
        file_path = service._get_strategy_path("MA Cross Strategy")
        assert file_path.exists()

    def test_export_strategy_creates_json_file(self):
        """export_strategy should create a .json file in strategies/ directory"""
        from src.data_service import DataService
        service = DataService()
        name = "Test Export Strategy"
        result = service._handle_request({
            "action": "export_strategy",
            "name": name,
            "description": "Test export",
            "params": {"fast_ma": 10, "slow_ma": 30, "initial_capital": 50000},
        })
        assert result["status"] == "ok"
        file_path = service._get_strategy_path(name)
        assert file_path.exists()
        assert file_path.suffix == ".json"
        # Clean up
        file_path.unlink(missing_ok=True)

    def test_export_strategy_stores_correct_fields(self):
        """export_strategy should store all required fields in the JSON file"""
        from src.data_service import DataService
        service = DataService()
        name = "Field Test Strategy"
        result = service._handle_request({
            "action": "export_strategy",
            "name": name,
            "version": "2.0",
            "description": "Testing field storage",
            "author": "tester",
            "params": {"fast_ma": 7, "slow_ma": 21},
            "indicators": ["ma5", "ma20", "rsi"],
            "entry_rule": "Test entry",
            "exit_rule": "Test exit",
        })
        assert result["status"] == "ok"

        file_path = service._get_strategy_path(name)
        assert file_path.exists()
        with open(file_path, "r") as f:
            data = json.load(f)

        assert data["name"] == name
        assert data["version"] == "2.0"
        assert data["description"] == "Testing field storage"
        assert data["author"] == "tester"
        assert data["params"]["fast_ma"] == 7
        assert data["params"]["slow_ma"] == 21
        assert data["indicators"] == ["ma5", "ma20", "rsi"]
        assert data["entry_rule"] == "Test entry"
        assert data["exit_rule"] == "Test exit"
        # Clean up
        file_path.unlink(missing_ok=True)


class TestStrategyImportAction:
    """Test import_strategy DataService action"""

    def test_import_strategy_action_exists(self):
        """DataService should have import_strategy action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "import_strategy" in service._actions

    def test_import_strategy_handler_exists(self):
        """DataService should have _handle_import_strategy method"""
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_import_strategy')

    def test_import_strategy_missing_data(self):
        """import_strategy without data should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "import_strategy"})
        assert result["status"] == "error"
        assert "data" in result["message"].lower()

    def test_import_strategy_from_dict(self):
        """import_strategy with dict data should succeed"""
        from src.data_service import DataService
        service = DataService()
        name = "Import Dict Test"
        result = service._handle_request({
            "action": "import_strategy",
            "data": {"name": name, "params": {"fast_ma": 5, "slow_ma": 20}},
        })
        assert result["status"] == "ok"
        assert result["data"]["name"] == name
        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)

    def test_import_strategy_from_json_string(self):
        """import_strategy with JSON string data should succeed"""
        from src.data_service import DataService
        service = DataService()
        name = "Import JSON Test"
        json_data = json.dumps({"name": name, "params": {"fast_ma": 10, "slow_ma": 30}})
        result = service._handle_request({
            "action": "import_strategy",
            "data": json_data,
        })
        assert result["status"] == "ok"
        assert result["data"]["name"] == name
        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)

    def test_import_strategy_invalid_json(self):
        """import_strategy with invalid JSON should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "import_strategy",
            "data": "not valid json {{{",
        })
        assert result["status"] == "error"

    def test_import_strategy_missing_name_in_data(self):
        """import_strategy with data missing name should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "import_strategy",
            "data": {"description": "No name here"},
        })
        assert result["status"] == "error"
        assert "name" in result["message"].lower()

    def test_import_strategy_defaults_fields(self):
        """import_strategy should fill in default values for missing optional fields"""
        from src.data_service import DataService
        service = DataService()
        name = "Defaults Test"
        result = service._handle_request({
            "action": "import_strategy",
            "data": {"name": name, "params": {}},
        })
        assert result["status"] == "ok"
        data = result["data"]
        assert data["version"] == "1.0"
        assert data["description"] == ""
        assert data["author"] == ""
        assert data["indicators"] == []
        assert data["entry_rule"] == ""
        assert data["exit_rule"] == ""
        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)


class TestListStrategiesAction:
    """Test list_strategies DataService action"""

    def test_list_strategies_action_exists(self):
        """DataService should have list_strategies action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "list_strategies" in service._actions

    def test_list_strategies_returns_list(self):
        """list_strategies should return a list"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "list_strategies"})
        assert result["status"] == "ok"
        assert isinstance(result["data"], list)

    def test_list_strategies_includes_exported(self):
        """list_strategies should include exported strategies"""
        from src.data_service import DataService
        service = DataService()
        name = "List Test Strategy"
        # Export a strategy first
        service._handle_request({
            "action": "export_strategy",
            "name": name,
            "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000},
        })
        # List should include it
        result = service._handle_request({"action": "list_strategies"})
        assert result["status"] == "ok"
        names = [s["name"] for s in result["data"]]
        assert name in names
        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)


class TestDeleteStrategyAction:
    """Test delete_strategy DataService action"""

    def test_delete_strategy_action_exists(self):
        """DataService should have delete_strategy action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "delete_strategy" in service._actions

    def test_delete_strategy_missing_name(self):
        """delete_strategy without name should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "delete_strategy"})
        assert result["status"] == "error"
        assert "name" in result["message"].lower()

    def test_delete_strategy_nonexistent(self):
        """delete_strategy for non-existent strategy should return error"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "delete_strategy",
            "name": "Nonexistent Strategy XYZ",
        })
        assert result["status"] == "error"

    def test_delete_strategy_success(self):
        """delete_strategy should remove the strategy file"""
        from src.data_service import DataService
        service = DataService()
        name = "Delete Test Strategy"
        # Export first
        service._handle_request({
            "action": "export_strategy",
            "name": name,
            "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000},
        })
        file_path = service._get_strategy_path(name)
        assert file_path.exists()

        # Delete
        result = service._handle_request({
            "action": "delete_strategy",
            "name": name,
        })
        assert result["status"] == "ok"
        assert not file_path.exists()


class TestStrategyStorage:
    """Test strategy storage (file system operations)"""

    def test_strategies_dir_created(self):
        """DataService init should create the strategies/ directory"""
        from src.data_service import DataService
        service = DataService()
        assert service._strategies_dir.exists()
        assert service._strategies_dir.is_dir()

    def test_strategy_path_sanitization(self):
        """Strategy file path should sanitize the name"""
        from src.data_service import DataService
        service = DataService()
        path = service._get_strategy_path("My Strategy!!!")
        assert "!" not in path.name
        assert ".json" in path.name

    def test_strategy_path_empty_name(self):
        """Strategy path with empty name should use 'unnamed'"""
        from src.data_service import DataService
        service = DataService()
        path = service._get_strategy_path("!!!")
        assert "unnamed" in path.name

    def test_load_all_strategies_empty(self):
        """_load_all_strategies should return empty list when no strategies exist"""
        from src.data_service import DataService
        service = DataService()
        # Clear the directory
        for f in service._strategies_dir.glob("*.json"):
            f.unlink(missing_ok=True)
        strategies = service._load_all_strategies()
        assert isinstance(strategies, list)

    def test_load_all_strategies_after_export(self):
        """_load_all_strategies should return exported strategies"""
        from src.data_service import DataService
        service = DataService()
        name = "Load Test Strategy"
        service._handle_request({
            "action": "export_strategy",
            "name": name,
            "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000},
        })
        strategies = service._load_all_strategies()
        names = [s["name"] for s in strategies]
        assert name in names
        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)


class TestStrategyFileFormat:
    """Test the strategy JSON file format"""

    def test_sample_strategy_has_required_fields(self):
        """Sample strategy should have all required fields"""
        required = ["name", "params"]
        for field in required:
            assert field in SAMPLE_STRATEGY, f"Missing required field: {field}"

    def test_sample_strategy_params(self):
        """Sample strategy params should include expected keys"""
        params = SAMPLE_STRATEGY["params"]
        assert "fast_ma" in params
        assert "slow_ma" in params
        assert "initial_capital" in params

    def test_strategy_json_roundtrip(self):
        """Strategy dict -> JSON string -> dict should be lossless"""
        json_str = json.dumps(SAMPLE_STRATEGY, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed == SAMPLE_STRATEGY

    def test_strategy_json_import_export_roundtrip(self):
        """Export then import should produce equivalent strategy"""
        from src.data_service import DataService
        service = DataService()
        name = "Roundtrip Strategy"
        # Export
        export_resp = service._handle_request({
            "action": "export_strategy",
            "name": name,
            "version": "1.0",
            "description": "Roundtrip test",
            "author": "tester",
            "params": {"fast_ma": 5, "slow_ma": 20, "initial_capital": 100000, "stop_loss_pct": -5.0},
            "indicators": ["ma5", "ma20"],
            "entry_rule": "MA5 crosses above MA20",
            "exit_rule": "MA5 crosses below MA20",
        })
        assert export_resp["status"] == "ok"
        exported = export_resp["data"]

        # Delete the file
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)

        # Import the exported data back
        import_resp = service._handle_request({
            "action": "import_strategy",
            "data": exported,
        })
        assert import_resp["status"] == "ok"
        imported = import_resp["data"]

        # Compare key fields
        for key in ["name", "version", "description", "author", "entry_rule", "exit_rule"]:
            assert imported.get(key) == exported.get(key), f"Mismatch on field: {key}"
        assert imported["params"]["fast_ma"] == exported["params"]["fast_ma"]
        assert imported["params"]["slow_ma"] == exported["params"]["slow_ma"]

        # Clean up
        file_path = service._get_strategy_path(name)
        file_path.unlink(missing_ok=True)
