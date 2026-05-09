"""Tests for src/shared/style.py"""
import pytest
from src.shared.style import (
    format_volume, format_market_cap, format_cny, format_pct,
    UP_ARROW, DOWN_ARROW, NEUTRAL_ARROW,
)

class TestFormatVolume:
    def test_large_volume_亿(self):
        assert format_volume(1.5e9) == "15.00亿"
    def test_medium_volume_万(self):
        assert format_volume(1.5e5) == "15.00万"
    def test_small_volume(self):
        assert format_volume(1234) == "1234"
    def test_none(self):
        assert format_volume(None) == "—"

class TestFormatMarketCap:
    def test_usd_trillion(self):
        assert format_market_cap(3e12, "US") == "$3.00T"
    def test_usd_billion(self):
        assert format_market_cap(5e9, "US") == "$5.00B"
    def test_cny_亿(self):
        assert format_market_cap(5e8, "CN") == "5.00亿"
    def test_none(self):
        assert format_market_cap(None, "CN") == "—"

class TestFormatPct:
    def test_positive(self):
        assert format_pct(2.5) == "+2.50%▲"
    def test_negative(self):
        assert format_pct(-1.5) == "-1.50%▼"
    def test_zero(self):
        assert format_pct(0) == "0.00%—"
    def test_none(self):
        assert format_pct(None) == "—%—"

class TestArrows:
    def test_arrows_defined(self):
        assert UP_ARROW == "▲"
        assert DOWN_ARROW == "▼"
        assert NEUTRAL_ARROW == "—"