"""Tests for src/shared/market_status.py"""
import pytest
from datetime import time
from src.shared.market_status import (
    get_china_status, get_hk_status, get_us_status, get_market_statuses, MarketStatus
)

class TestGetChinaStatus:
    def test_open_session_morning(self):
        assert get_china_status(time(10, 0)) == MarketStatus.OPEN
    def test_open_session_afternoon(self):
        assert get_china_status(time(14, 0)) == MarketStatus.OPEN
    def test_pre_open(self):
        assert get_china_status(time(9, 20)) == MarketStatus.PRE_CLOSE
    def test_lunch(self):
        assert get_china_status(time(12, 0)) == MarketStatus.LUNCH
    def test_after_close(self):
        assert get_china_status(time(15, 30)) == MarketStatus.CLOSED
    def test_night(self):
        assert get_china_status(time(20, 0)) == MarketStatus.CLOSED

class TestGetHkStatus:
    def test_open_morning(self):
        assert get_hk_status(time(10, 0)) == MarketStatus.OPEN
    def test_lunch(self):
        assert get_hk_status(time(12, 30)) == MarketStatus.LUNCH
    def test_open_afternoon(self):
        assert get_hk_status(time(14, 0)) == MarketStatus.OPEN
    def test_closed(self):
        assert get_hk_status(time(8, 0)) == MarketStatus.CLOSED

class TestGetMarketStatuses:
    def test_returns_all_three_markets(self):
        result = get_market_statuses()
        assert set(result.keys()) == {"A股", "港股", "美股"}
    def test_each_has_emoji_text_color(self):
        result = get_market_statuses()
        for market, info in result.items():
            assert "emoji" in info
            assert "text" in info
            assert "color" in info