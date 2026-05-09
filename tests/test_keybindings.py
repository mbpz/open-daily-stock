# -*- coding: utf-8 -*-
"""Keybindings 模块测试"""
import pytest
from unittest.mock import patch, MagicMock

from src.shared.keybindings import get_keybinding, get_all_keybindings


class TestGetKeybinding:
    """get_keybinding 函数测试"""

    def test_get_keybinding_returns_configured_value(self):
        """配置中存在时返回对应按键"""
        mock_config = MagicMock()
        mock_config.keybindings = {
            "global": {"quit": "q", "refresh": "r"},
            "markets": {"move_up": "up"},
        }
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            assert get_keybinding("global", "quit") == "q"
            assert get_keybinding("global", "refresh") == "r"
            assert get_keybinding("markets", "move_up") == "up"

    def test_get_keybinding_returns_none_for_missing_section(self):
        """不存在的 section 返回 None"""
        mock_config = MagicMock()
        mock_config.keybindings = {"global": {"quit": "q"}}
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            assert get_keybinding("nonexistent", "quit") is None

    def test_get_keybinding_returns_none_for_missing_action(self):
        """section 中存在但 action 不存在时返回 None"""
        mock_config = MagicMock()
        mock_config.keybindings = {"global": {"quit": "q"}}
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            assert get_keybinding("global", "nonexistent") is None

    def test_get_keybinding_handles_attribute_error(self):
        """keybindings 属性缺失时返回 None（向后兼容）"""
        mock_config = MagicMock(spec=[])  # 无 keybindings 属性
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            assert get_keybinding("global", "quit") is None

    def test_get_keybinding_returns_none_for_empty_config(self):
        """空 keybindings 配置时返回 None"""
        mock_config = MagicMock()
        mock_config.keybindings = {}
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            assert get_keybinding("global", "quit") is None


class TestGetAllKeybindings:
    """get_all_keybindings 函数测试"""

    def test_get_all_keybindings_returns_dict(self):
        """返回指定 section 的所有 keybindings"""
        mock_config = MagicMock()
        mock_config.keybindings = {
            "global": {"quit": "q", "refresh": "r", "help": "?"},
        }
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            result = get_all_keybindings("global")
            assert isinstance(result, dict)
            assert result == {"quit": "q", "refresh": "r", "help": "?"}

    def test_get_all_keybindings_empty_for_missing_section(self):
        """不存在的 section 返回空字典"""
        mock_config = MagicMock()
        mock_config.keybindings = {"global": {"quit": "q"}}
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            result = get_all_keybindings("nonexistent")
            assert result == {}

    def test_get_all_keybindings_handles_attribute_error(self):
        """keybindings 属性缺失时返回空字典"""
        mock_config = MagicMock(spec=[])
        with patch("src.shared.keybindings.get_config", return_value=mock_config):
            result = get_all_keybindings("global")
            assert result == {}


class TestDefaultConfigSections:
    """默认配置结构测试"""

    def test_default_config_has_expected_sections(self):
        """默认配置包含所有预期的 section"""
        from src.config import Config
        # 构造一个不加载 config.json 的默认实例
        config = Config()
        kbs = config.keybindings
        assert isinstance(kbs, dict)
        assert "global" in kbs
        assert "markets" in kbs
        assert "analysis" in kbs
        assert "tasks" in kbs

    def test_default_global_section_has_essential_actions(self):
        """global section 包含基本的动作绑定"""
        from src.config import Config
        config = Config()
        global_kb = config.keybindings["global"]
        essential = ["quit", "refresh", "help", "toggle_theme"]
        for action in essential:
            assert action in global_kb, f"global section 缺少 {action}"

    def test_default_markets_section_has_navigation_actions(self):
        """markets section 包含导航相关动作"""
        from src.config import Config
        config = Config()
        markets_kb = config.keybindings["markets"]
        nav_actions = ["move_up", "move_down", "select", "back"]
        for action in nav_actions:
            assert action in markets_kb, f"markets section 缺少 {action}"


class TestDataServiceGetKeybindingsAction:
    """DataService get_keybindings action 测试"""

    def test_data_service_get_keybindings_action(self):
        """_handle_get_keybindings 返回正确的 keybindings 数据"""
        from src.data_service import DataService
        from src.config import Config

        # 使用测试专用 json 路径，避免加载真实 config.json
        Config.reset_instance()
        Config._json_path = None  # 不加载任何 config.json

        svc = DataService()
        result = svc._handle_get_keybindings({"section": "global"})
        assert result["status"] == "ok"
        assert "data" in result
        assert isinstance(result["data"], dict)
        assert "quit" in result["data"]
        assert result["data"]["quit"] == "q"

    def test_data_service_get_keybindings_default_section(self):
        """不传 section 时默认返回 global section"""
        from src.data_service import DataService
        from src.config import Config

        Config.reset_instance()
        Config._json_path = None

        svc = DataService()
        result = svc._handle_get_keybindings({})
        assert result["status"] == "ok"
        assert "data" in result
        assert "quit" in result["data"]


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_flat_keybindings_migration(self):
        """旧版 flat keybindings 自动迁移为 nested 格式"""
        from src.config import Config
        import json
        from pathlib import Path
        import tempfile
        import os

        old_flat = {
            "keybindings": {"q": "quit", "r": "refresh", "?": "help"},
            "theme": "dark",
        }

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(old_flat, f)
            tmp_path = f.name

        try:
            Config.reset_instance()
            Config._json_path = Path(tmp_path)
            config = Config()
            Config.load_json_config(config)

            kbs = config.keybindings
            assert isinstance(kbs, dict)
            # 迁移后应为嵌套格式
            assert "global" in kbs
            global_kb = kbs["global"]
            assert global_kb["quit"] == "q"
            assert global_kb["refresh"] == "r"
            assert global_kb["help"] == "?"
        finally:
            os.unlink(tmp_path)

    def test_already_nested_format_preserved(self):
        """已是嵌套格式的 keybindings 保持不变"""
        from src.config import Config
        import json
        from pathlib import Path
        import tempfile
        import os

        new_nested = {
            "keybindings": {
                "global": {"quit": "x", "refresh": "f5"},
                "markets": {"move_up": "k"},
            },
            "theme": "light",
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(new_nested, f)
            tmp_path = f.name

        try:
            Config.reset_instance()
            Config._json_path = Path(tmp_path)
            config = Config()
            Config.load_json_config(config)

            kbs = config.keybindings
            assert "global" in kbs
            assert kbs["global"]["quit"] == "x"
            assert kbs["global"]["refresh"] == "f5"
            assert "markets" in kbs
            assert kbs["markets"]["move_up"] == "k"
        finally:
            os.unlink(tmp_path)
