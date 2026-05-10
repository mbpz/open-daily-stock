"""Tests for shared theme module and DataService theme handlers."""
import pytest
from unittest.mock import patch, MagicMock

from src.shared.theme import (
    DARK_THEME, LIGHT_THEME, get_theme, get_current_theme,
)
from src.config import Config


_REQUIRED_KEYS = [
    "bg", "bg_card", "bg_input", "fg", "fg_secondary",
    "accent", "danger", "warning", "border",
    "up", "down", "neutral",
]


class TestThemeDicts:
    """Test theme constants."""

    def test_dark_theme_has_all_keys(self):
        for key in _REQUIRED_KEYS:
            assert key in DARK_THEME, f"Missing key '{key}' in DARK_THEME"

    def test_light_theme_has_all_keys(self):
        for key in _REQUIRED_KEYS:
            assert key in LIGHT_THEME, f"Missing key '{key}' in LIGHT_THEME"

    def test_theme_colors_are_valid_hex(self):
        """All theme values should be valid CSS hex colors."""
        for theme in (DARK_THEME, LIGHT_THEME):
            for key, val in theme.items():
                assert val.startswith("#"), f"{key} value '{val}' is not hex"
                assert len(val) == 7, f"{key} value '{val}' has wrong length"


class TestGetTheme:
    """Test get_theme() function."""

    def test_get_theme_dark(self):
        result = get_theme("dark")
        assert result is DARK_THEME

    def test_get_theme_light(self):
        result = get_theme("light")
        assert result is LIGHT_THEME

    def test_get_theme_invalid_defaults_to_dark(self):
        result = get_theme("neon")
        assert result is DARK_THEME

    def test_get_theme_default_arg(self):
        result = get_theme()
        assert result is DARK_THEME


class TestGetCurrentTheme:
    """Test get_current_theme() reads from config."""

    def test_get_current_theme_reads_config_dark(self):
        """get_current_theme returns DARK_THEME when config.theme is 'dark'."""
        config = Config.__new__(Config)
        config.theme = "dark"
        with patch("src.shared.theme.get_config", return_value=config):
            result = get_current_theme()
        assert result is DARK_THEME

    def test_get_current_theme_reads_config_light(self):
        """get_current_theme returns LIGHT_THEME when config.theme is 'light'."""
        config = Config.__new__(Config)
        config.theme = "light"
        with patch("src.shared.theme.get_config", return_value=config):
            result = get_current_theme()
        assert result is LIGHT_THEME


class TestDataServiceThemeActions:
    """Test DataService get_theme and set_theme action handlers."""

    def test_data_service_get_theme(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_theme"})
        assert result["status"] == "ok"
        assert "data" in result
        assert "theme" in result["data"]
        assert "colors" in result["data"]
        assert result["data"]["theme"] in ("dark", "light")

    def test_data_service_set_theme_valid(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "set_theme", "theme": "light"})
        assert result["status"] == "ok"
        assert result["theme"] == "light"

    def test_data_service_set_theme_invalid(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "set_theme", "theme": "neon"})
        assert result["status"] == "error"
        assert "dark" in result["message"] or "light" in result["message"]

    def test_data_service_set_theme_persists_to_config(self):
        from src.data_service import DataService
        service = DataService()
        # Set to light
        result = service._handle_request({"action": "set_theme", "theme": "light"})
        assert result["status"] == "ok"
        # Now get_theme should reflect the change
        result2 = service._handle_request({"action": "get_theme"})
        assert result2["data"]["theme"] == "light"
        # Restore to dark so we don't leave side effects
        service._handle_request({"action": "set_theme", "theme": "dark"})
