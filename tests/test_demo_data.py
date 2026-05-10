# -*- coding: utf-8 -*-
"""Tests for demo data module (P5-4)."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src import demo_data
from src.config import Config


class TestDemoStocks:
    """Test DEMO_STOCKS data validity."""

    def test_five_stocks_defined(self):
        """DEMO_STOCKS contains exactly 5 stocks."""
        assert len(demo_data.DEMO_STOCKS) == 5

    def test_each_stock_has_required_fields(self):
        """Each stock has code, name, price, change, pe, market_cap, volume."""
        required = {"code", "name", "market", "price", "change",
                     "pe", "market_cap", "volume", "industry"}
        for stock in demo_data.DEMO_STOCKS:
            assert required.issubset(stock.keys()), (
                f"Stock {stock.get('code', '?')} missing fields: {required - set(stock.keys())}"
            )

    def test_expected_stock_codes(self):
        """Check that expected demo stocks are present."""
        codes = {s["code"] for s in demo_data.DEMO_STOCKS}
        assert codes == {"600519", "000001", "00700", "AAPL", "000858"}

    def test_prices_are_positive(self):
        """All stock prices are positive."""
        for stock in demo_data.DEMO_STOCKS:
            assert stock["price"] > 0

    def test_pe_values_reasonable(self):
        """PE values are positive floats."""
        for stock in demo_data.DEMO_STOCKS:
            assert isinstance(stock["pe"], (int, float))
            assert stock["pe"] > 0


class TestDemoKlines:
    """Test DEMO_KLINES data."""

    def test_klines_for_all_five_stocks(self):
        """K-lines exist for all 5 demo stocks."""
        assert set(demo_data.DEMO_KLINES.keys()) == {"600519", "000001", "00700", "AAPL", "000858"}

    def test_each_kline_has_60_days(self):
        """Each stock has 60 trading days of K-line data."""
        for code, klines in demo_data.DEMO_KLINES.items():
            assert len(klines) == 60, f"{code} has {len(klines)} klines, expected 60"

    def test_kline_record_format(self):
        """Each K-line record has 6 fields: [date, open, high, low, close, volume]."""
        for klines in demo_data.DEMO_KLINES.values():
            for record in klines:
                assert len(record) == 6
                assert isinstance(record[0], str)  # date
                assert isinstance(record[1], (int, float))  # open
                assert isinstance(record[2], (int, float))  # high
                assert isinstance(record[3], (int, float))  # low
                assert isinstance(record[4], (int, float))  # close
                assert isinstance(record[5], int)  # volume
                # High >= Low
                assert record[2] >= record[3], (
                    f"High ({record[2]}) < Low ({record[3]}) in {record[0]}"
                )

    def test_kline_dates_are_sequential(self):
        """Dates in K-line data are sequential."""
        for klines in demo_data.DEMO_KLINES.values():
            dates = [r[0] for r in klines]
            for i in range(1, len(dates)):
                assert dates[i] > dates[i-1], f"Non-sequential: {dates[i-1]} -> {dates[i]}"


class TestDemoAiAnalyses:
    """Test DEMO_AI_ANALYSES data."""

    def test_analyses_for_all_five_stocks(self):
        """AI analyses exist for all 5 stocks."""
        assert set(demo_data.DEMO_AI_ANALYSES.keys()) == {"600519", "000001", "00700", "AAPL", "000858"}

    def test_each_analysis_has_required_fields(self):
        """Each analysis has required fields."""
        required = {"code", "name", "sentiment_score", "trend_prediction",
                     "operation_advice", "confidence", "analysis_summary"}
        for code, analysis in demo_data.DEMO_AI_ANALYSES.items():
            assert required.issubset(analysis.keys()), (
                f"{code} missing: {required - set(analysis.keys())}"
            )

    def test_sentiment_scores_in_range(self):
        """Sentiment scores are between 0 and 100."""
        for analysis in demo_data.DEMO_AI_ANALYSES.values():
            assert 0 <= analysis["sentiment_score"] <= 100

    def test_confidence_in_range(self):
        """Confidence scores are between 0 and 100."""
        for analysis in demo_data.DEMO_AI_ANALYSES.values():
            assert 0 <= analysis["confidence"] <= 100

    def test_model_used_is_demo_indicator(self):
        """Model used indicates demo data."""
        for analysis in demo_data.DEMO_AI_ANALYSES.values():
            assert "(演示数据)" in analysis.get("model_used", "")


class TestDemoPortfolio:
    """Test DEMO_PORTFOLIO data."""

    def test_five_positions(self):
        """Portfolio has 5 positions."""
        assert len(demo_data.DEMO_PORTFOLIO) == 5

    def test_each_position_has_required_fields(self):
        """Each position has required fields."""
        required = {"code", "name", "shares", "cost", "current_price"}
        for pos in demo_data.DEMO_PORTFOLIO:
            assert required.issubset(pos.keys())

    def test_positive_shares_and_prices(self):
        """All positions have positive shares and prices."""
        for pos in demo_data.DEMO_PORTFOLIO:
            assert pos["shares"] > 0
            assert pos["cost"] > 0
            assert pos["current_price"] > 0

    def test_portfolio_summary_exists(self):
        """Portfolio summary has expected fields."""
        summary = demo_data.DEMO_PORTFOLIO_SUMMARY
        assert "total_market_value" in summary
        assert "total_cost" in summary
        assert "total_profit" in summary
        assert "total_assets" in summary
        assert summary["total_assets"] > summary["total_market_value"]  # includes cash


class TestApplyDemoMode:
    """Test apply_demo_mode and exit_demo_mode functions."""

    def test_apply_demo_mode_sets_mode(self):
        """apply_demo_mode sets config.mode to 'demo'."""
        config = Config.__new__(Config)
        config.mode = None
        config.stock_list = []
        config.save_json_config = MagicMock()

        demo_data.apply_demo_mode(config)

        assert config.mode == "demo"
        assert config.stock_list == ["600519", "000001", "00700", "AAPL", "000858"]
        config.save_json_config.assert_called_once_with({"mode": "demo"})

    def test_exit_demo_mode_clears_mode(self):
        """exit_demo_mode sets config.mode to None."""
        config = Config.__new__(Config)
        config.mode = "demo"
        config.save_json_config = MagicMock()

        demo_data.exit_demo_mode(config)

        assert config.mode is None
        config.save_json_config.assert_called_once_with({"mode": "live"})


class TestConfigDemoMode:
    """Test Config demo mode integration."""

    def test_is_demo_mode_returns_true_when_mode_is_demo(self):
        """is_demo_mode returns True when mode == 'demo'."""
        config = Config.__new__(Config)
        config.mode = "demo"
        assert config.is_demo_mode() is True

    def test_is_demo_mode_returns_false_when_mode_is_none(self):
        """is_demo_mode returns False when mode is None."""
        config = Config.__new__(Config)
        config.mode = None
        assert config.is_demo_mode() is False

    def test_is_demo_mode_returns_false_when_mode_is_live(self):
        """is_demo_mode returns False when mode == 'live'."""
        config = Config.__new__(Config)
        config.mode = "live"
        assert config.is_demo_mode() is False

    def test_is_first_time_setup_false_in_demo_mode(self):
        """is_first_time_setup returns False when in demo mode."""
        config = Config.__new__(Config)
        config.mode = "demo"
        config.gemini_api_key = None
        config.openai_api_key = None
        config.stock_list = ["600519"]

        result = config.is_first_time_setup()
        assert result is False

    def test_validate_no_api_key_warning_in_demo_mode(self):
        """validate does not warn about missing API key in demo mode."""
        config = Config.__new__(Config)
        config.mode = "demo"
        config.gemini_api_key = None
        config.openai_api_key = None
        config.stock_list = ["600519"]
        config.bocha_api_keys = []
        config.tavily_api_keys = []
        config.serpapi_keys = []
        config.tushare_token = None
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None
        config.telegram_bot_token = None
        config.telegram_chat_id = None
        config.email_sender = None
        config.email_password = None
        config.pushover_user_key = None
        config.pushover_api_token = None
        config.pushplus_token = None
        config.custom_webhook_urls = []
        config.custom_webhook_bearer_token = None
        config.discord_bot_token = None
        config.discord_main_channel_id = None
        config.discord_webhook_url = None

        warnings = config.validate()
        # Should NOT contain AI API key warning (Gemini/OpenAI)
        ai_warning = [w for w in warnings if "Gemini" in w or "OpenAI" in w]
        assert len(ai_warning) == 0, (
            f"Demo mode should not warn about AI API keys: {ai_warning}"
        )
        # Other warnings (search engine keys, etc.) are fine in demo mode
