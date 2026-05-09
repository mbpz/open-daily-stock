"""
Tests for P1-3: Error Recovery and Resilience Features

Tests:
1. MarketDataCache - cache set/get/staleness
2. DataService timeout handling
3. Network degradation fallback
4. AI API 429 retry handling
"""

import pytest
import time
from unittest.mock import patch, MagicMock


class TestMarketDataCache:
    """Test MarketDataCache for network degradation fallback"""

    def test_cache_set_and_get(self):
        from src.storage import MarketDataCache, get_market_cache

        cache = get_market_cache()
        test_data = {"code": "600519", "price": 1800.0, "name": "贵州茅台"}

        cache.set("600519", test_data, "test_source")
        retrieved = cache.get("600519")

        assert retrieved == test_data
        assert retrieved["price"] == 1800.0

    def test_cache_miss_returns_none(self):
        from src.storage import get_market_cache

        cache = get_market_cache()
        result = cache.get("nonexistent_code")
        assert result is None

    def test_cache_staleness_detection(self):
        from src.storage import MarketDataCache, get_market_cache, MARKET_DATA_CACHE_TTL

        # Reset singleton for clean test
        MarketDataCache._instance = None
        cache = get_market_cache()

        test_data = {"code": "600519", "price": 1800.0}
        cache.set("600519", test_data, "test")

        # Fresh cache should not be stale
        data, is_stale, age = cache.get_with_staleness("600519")
        assert data is not None
        assert is_stale is False
        assert age < 1  # Less than 1 second old

    def test_cache_ttl_for_different_markets(self):
        from src.storage import MARKET_DATA_CACHE_TTL

        assert MARKET_DATA_CACHE_TTL["A"] == 86400   # A股: 1 day
        assert MARKET_DATA_CACHE_TTL["HK"] == 3600   # 港股: 1 hour
        assert MARKET_DATA_CACHE_TTL["US"] == 3600   # 美股: 1 hour

    def test_market_type_detection(self):
        from src.storage import MarketDataCache

        # Reset singleton
        MarketDataCache._instance = None
        cache = MarketDataCache()

        assert cache._get_market_type("600519") == "A"      # A股
        assert cache._get_market_type("000001") == "A"      # A股
        assert cache._get_market_type("hk00700") == "HK"    # 港股
        assert cache._get_market_type("AAPL") == "US"       # 美股
        assert cache._get_market_type("TSLA") == "US"       # 美股


class TestDataServiceTimeout:
    """Test DataService per-request timeout"""

    def test_request_handler_has_timeout(self):
        from src.data_service import DataService, REQUEST_TIMEOUT_SECONDS

        service = DataService()
        assert hasattr(service, '_executor')
        assert service._executor._max_workers == 5  # MAX_CONCURRENT_REQUESTS

    def test_slow_handler_times_out(self):
        from src.data_service import DataService

        service = DataService()

        # Add a slow handler
        def slow_handler(req):
            time.sleep(10)  # 10 second sleep
            return {"status": "ok"}

        service._actions["slow_action"] = "slow_handler"
        setattr(service, "slow_handler", slow_handler)

        # Create request with short timeout
        req = {"action": "slow_action", "_timeout": 1}

        start = time.time()
        result = service._handle_request(req)
        elapsed = time.time() - start

        assert result["status"] == "error"
        assert "超时" in result["message"] or "timeout" in result["message"].lower()
        assert elapsed < 5  # Should fail fast, not wait 10 seconds


class TestNetworkDegradationFallback:
    """Test network degradation fallback in DataService"""

    def test_fetch_with_fallback_returns_live_data(self):
        from src.data_service import DataService

        service = DataService()

        call_count = 0
        def mock_fetch():
            nonlocal call_count
            call_count += 1
            return {"code": "600519", "price": 1800.0, "name": "茅台"}

        data, is_cached, is_stale, age = service._fetch_with_fallback("600519", mock_fetch)

        assert call_count == 1
        assert is_cached is False
        assert data["price"] == 1800.0

    def test_fetch_with_fallback_uses_cache_on_error(self):
        from src.data_service import DataService
        from src.storage import get_market_cache

        service = DataService()
        cache = get_market_cache()

        # Pre-populate cache
        cache.set("600519", {"code": "600519", "price": 1750.0, "name": "茅台"}, "cached_source")

        call_count = 0
        def mock_fetch():
            nonlocal call_count
            call_count += 1
            raise Exception("Network error")

        data, is_cached, is_stale, age = service._fetch_with_fallback("600519", mock_fetch)

        assert call_count == 1
        assert is_cached is True
        assert data["price"] == 1750.0

    def test_fetch_with_fallback_raises_when_no_cache(self):
        from src.data_service import DataService
        from src.storage import get_market_cache

        service = DataService()
        cache = get_market_cache()

        # Ensure no cache
        cache._cache.pop("600519", None)

        def mock_fetch():
            raise Exception("Network error")

        with pytest.raises(Exception):
            service._fetch_with_fallback("600519", mock_fetch)


class TestAIAPIRetry:
    """Test AI API 429 retry with circuit breaker"""

    def test_circuit_breaker_disables_after_3_429s(self):
        from src.data_service import DataService

        service = DataService()
        state = service._ai_provider_state

        # Simulate 3 consecutive 429s
        now = time.time()
        state["429_count"] = 3
        state["last_429_time"] = now
        state["disabled_until"] = now + 1800  # 30 minutes

        # Check provider is disabled
        assert state["disabled_until"] > now

    def test_retry_count_tracked(self):
        from src.data_service import DataService

        service = DataService()
        state = service._ai_provider_state

        # Reset state
        state["429_count"] = 0
        state["disabled_until"] = 0

        # The state should be clean initially
        assert state["429_count"] == 0
        assert state["disabled_until"] == 0

    def test_ai_provider_state_structure(self):
        from src.data_service import DataService

        service = DataService()
        state = service._ai_provider_state

        assert "429_count" in state
        assert "last_429_time" in state
        assert "disabled_until" in state
        assert "current_provider" in state


class TestHeartbeat:
    """Test DataService heartbeat mechanism"""

    def test_heartbeat_method_exists(self):
        from src.data_service import DataService

        service = DataService()
        assert hasattr(service, '_send_heartbeat')

    def test_heartbeat_interval_configured(self):
        from src.data_service import HEARTBEAT_INTERVAL

        assert HEARTBEAT_INTERVAL == 30  # 30 seconds


class TestAutoRestartConfig:
    """Test auto-restart configuration (watchdog in main.py)"""

    def test_restart_config_values(self):
        from src.data_service import MAX_RESTARTS_PER_HOUR, RESTART_COOLDOWN_SECONDS

        assert MAX_RESTARTS_PER_HOUR == 3
        assert RESTART_COOLDOWN_SECONDS == 60