# -*- coding: utf-8 -*-
"""ProviderRegistry 和 DataProviderPlugin 插件架构测试"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import logging

from src.data_provider.plugin import DataProviderPlugin, ProviderRegistry


# ============================================================
# Mock Provider 实现 (用于测试)
# ============================================================

class MockCNProvider(DataProviderPlugin):
    """模拟 A 股数据源"""

    def __init__(self, name="MockCN", priority=10, available=True,
                 fetch_daily_result=None):
        self._name = name
        self._priority = priority
        self._available = available
        self._fetch_daily_result = fetch_daily_result

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def market(self) -> str:
        return "CN"

    def is_available(self) -> bool:
        return self._available

    def fetch_daily(self, code: str, days: int = 1):
        return self._fetch_daily_result


class MockHKProvider(DataProviderPlugin):
    """模拟港股数据源"""

    def __init__(self, name="MockHK", priority=20, available=True):
        self._name = name
        self._priority = priority
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def market(self) -> str:
        return "HK"

    def is_available(self) -> bool:
        return self._available

    def fetch_daily(self, code: str, days: int = 1):
        return None


class MockUSProvider(DataProviderPlugin):
    """模拟美股数据源"""

    def __init__(self, name="MockUS", priority=30, available=True):
        self._name = name
        self._priority = priority
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def market(self) -> str:
        return "US"

    def is_available(self) -> bool:
        return self._available

    def fetch_daily(self, code: str, days: int = 1):
        return None


class MockAllProvider(DataProviderPlugin):
    """模拟全市场数据源"""

    def __init__(self, name="MockAll", priority=5, available=True,
                 fetch_daily_result=None):
        self._name = name
        self._priority = priority
        self._available = available
        self._fetch_daily_result = fetch_daily_result

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def market(self) -> str:
        return "ALL"

    def is_available(self) -> bool:
        return self._available

    def fetch_daily(self, code: str, days: int = 1):
        return self._fetch_daily_result


class MockFailingProvider(DataProviderPlugin):
    """模拟总是失败的数据源"""

    @property
    def name(self) -> str:
        return "MockFailing"

    @property
    def priority(self) -> int:
        return 1

    @property
    def market(self) -> str:
        return "CN"

    def is_available(self) -> bool:
        return True

    def fetch_daily(self, code: str, days: int = 1):
        raise RuntimeError("Simulated failure")


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前重置注册中心"""
    ProviderRegistry.reset()
    yield
    ProviderRegistry.reset()


@pytest.fixture
def registry():
    return ProviderRegistry.get_instance()


# ============================================================
# Test Cases
# ============================================================

class TestProviderRegistration:
    """测试插件注册/注销"""

    def test_register_provider(self, registry):
        """测试注册一个数据源"""
        provider = MockCNProvider(name="TestProvider", priority=10)
        registry.register(provider)

        assert registry.get_provider("TestProvider") is provider

    def test_register_multiple_providers(self, registry):
        """测试注册多个数据源"""
        p1 = MockCNProvider(name="ProviderA", priority=10)
        p2 = MockHKProvider(name="ProviderB", priority=20)

        registry.register(p1)
        registry.register(p2)

        assert registry.get_provider("ProviderA") is p1
        assert registry.get_provider("ProviderB") is p2

    def test_unregister_provider(self, registry):
        """测试注销数据源"""
        provider = MockCNProvider(name="ToRemove")
        registry.register(provider)
        registry.unregister("ToRemove")

        assert registry.get_provider("ToRemove") is None

    def test_unregister_nonexistent(self, registry):
        """测试注销不存在的数据源（不应报错）"""
        registry.unregister("DoesNotExist")

    def test_duplicate_register_warns(self, registry, caplog):
        """测试重复注册同名数据源产生警告"""
        p1 = MockCNProvider(name="SameName", priority=10)
        p2 = MockCNProvider(name="SameName", priority=20)

        with caplog.at_level(logging.WARNING):
            registry.register(p1)
            registry.register(p2)

        assert "already registered" in caplog.text

    def test_get_provider_nonexistent(self, registry):
        """测试获取不存在的数据源返回 None"""
        assert registry.get_provider("NonExistent") is None

    def test_singleton_pattern(self):
        """测试单例模式"""
        r1 = ProviderRegistry()
        r2 = ProviderRegistry()
        r3 = ProviderRegistry.get_instance()

        assert r1 is r2
        assert r2 is r3

    def test_reset_registry(self, registry):
        """测试重置注册中心"""
        registry.register(MockCNProvider(name="Test"))
        assert registry.get_provider("Test") is not None

        ProviderRegistry.reset()
        new_registry = ProviderRegistry.get_instance()
        assert new_registry.get_provider("Test") is None


class TestProviderListing:
    """测试数据源列表查询"""

    def test_list_providers_sorted_by_priority(self, registry):
        """测试按优先级排序"""
        registry.register(MockCNProvider(name="Low", priority=30))
        registry.register(MockCNProvider(name="High", priority=10))
        registry.register(MockCNProvider(name="Highest", priority=5))

        providers = registry.list_providers()
        names = [p.name for p in providers]
        priorities = [p.priority for p in providers]

        assert names == ["Highest", "High", "Low"]
        assert priorities == [5, 10, 30]

    def test_list_providers_filtered_by_market_cn(self, registry):
        """测试按市场过滤 - CN"""
        registry.register(MockCNProvider(name="CN1", priority=10))
        registry.register(MockHKProvider(name="HK1", priority=20))
        registry.register(MockUSProvider(name="US1", priority=30))

        providers = registry.list_providers(market="CN")
        names = [p.name for p in providers]

        assert len(providers) == 1
        assert "CN1" in names
        assert "HK1" not in names

    def test_list_providers_filtered_by_market_hk(self, registry):
        """测试按市场过滤 - HK"""
        registry.register(MockCNProvider(name="CN1"))
        registry.register(MockHKProvider(name="HK1"))

        providers = registry.list_providers(market="HK")
        names = [p.name for p in providers]

        assert len(providers) == 1
        assert names == ["HK1"]

    def test_list_providers_all_market_includes_all(self, registry):
        """测试 'ALL' 市场的数据源在所有过滤器中都出现"""
        registry.register(MockCNProvider(name="CN1"))
        registry.register(MockAllProvider(name="All1"))

        cn_providers = registry.list_providers(market="CN")
        hk_providers = registry.list_providers(market="HK")

        cn_names = [p.name for p in cn_providers]
        hk_names = [p.name for p in hk_providers]

        assert "All1" in cn_names
        assert "All1" in hk_names

    def test_list_providers_empty_registry(self, registry):
        """测试空注册中心返回空列表"""
        assert registry.list_providers() == []

    def test_list_providers_no_match(self, registry):
        """测试没有匹配的数据源"""
        registry.register(MockCNProvider(name="CN1"))
        providers = registry.list_providers(market="HK")
        assert providers == []


class TestAvailableProviders:
    """测试可用数据源查询"""

    def test_get_available_providers(self, registry):
        """测试获取可用数据源"""
        registry.register(MockCNProvider(name="Available", available=True))
        registry.register(MockCNProvider(name="Unavailable", available=False))

        available = registry.get_available_providers()
        names = [p.name for p in available]

        assert len(available) == 1
        assert "Available" in names
        assert "Unavailable" not in names

    def test_get_available_providers_all_available(self, registry):
        """测试所有数据源都可用"""
        registry.register(MockCNProvider(name="A", available=True))
        registry.register(MockCNProvider(name="B", available=True))

        available = registry.get_available_providers()
        assert len(available) == 2

    def test_get_available_providers_none_available(self, registry):
        """测试所有数据源都不可用"""
        registry.register(MockCNProvider(name="A", available=False))
        registry.register(MockCNProvider(name="B", available=False))

        available = registry.get_available_providers()
        assert available == []

    def test_get_available_providers_with_market_filter(self, registry):
        """测试按市场过滤可用数据源"""
        registry.register(MockCNProvider(name="CN", available=True))
        registry.register(MockHKProvider(name="HK", available=True))

        available = registry.get_available_providers(market="CN")
        names = [p.name for p in available]

        assert names == ["CN"]


class TestFetchWithFallback:
    """测试故障切换机制"""

    def test_fetch_with_fallback_first_succeeds(self, registry):
        """测试第一个数据源成功"""
        import pandas as pd
        expected_df = pd.DataFrame({"close": [100, 101]})

        registry.register(MockCNProvider(
            name="Provider1", priority=10,
            fetch_daily_result=expected_df,
        ))
        registry.register(MockCNProvider(
            name="Provider2", priority=20,
            fetch_daily_result=None,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily", days=10,
        )

        assert result["status"] == "ok"
        assert result["provider"] == "Provider1"
        assert result["data"] is expected_df

    def test_fetch_with_fallback_second_succeeds(self, registry):
        """测试第一个失败，第二个成功后"""
        import pandas as pd
        expected_df = pd.DataFrame({"close": [200, 201]})

        registry.register(MockCNProvider(
            name="Provider1", priority=10,
            fetch_daily_result=None,  # returns None = failure
        ))
        registry.register(MockCNProvider(
            name="Provider2", priority=20,
            fetch_daily_result=expected_df,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "ok"
        assert result["provider"] == "Provider2"
        assert result["data"] is expected_df

    def test_fetch_with_fallback_all_fail(self, registry):
        """测试所有数据源都失败"""
        registry.register(MockCNProvider(
            name="Provider1", priority=10,
            fetch_daily_result=None,
        ))
        registry.register(MockCNProvider(
            name="Provider2", priority=20,
            fetch_daily_result=None,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "error"
        assert len(result["errors"]) == 0  # No exceptions, just no results

    def test_fetch_with_fallback_exception_handled(self, registry):
        """测试异常被捕获"""
        import pandas as pd
        expected_df = pd.DataFrame({"close": [300]})

        registry.register(MockFailingProvider())
        registry.register(MockCNProvider(
            name="Fallback", priority=50,
            fetch_daily_result=expected_df,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "ok"
        assert result["provider"] == "Fallback"

    def test_fetch_with_fallback_all_exceptions(self, registry):
        """测试所有数据源都抛异常"""
        registry.register(MockFailingProvider())

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "error"
        assert len(result["errors"]) == 1
        assert "Simulated failure" in result["errors"][0]

    def test_fetch_with_fallback_market_filter(self, registry):
        """测试按市场过滤"""
        import pandas as pd
        expected_df = pd.DataFrame({"close": [400]})

        registry.register(MockHKProvider(name="HK1", priority=10))
        registry.register(MockCNProvider(
            name="CN1", priority=20,
            fetch_daily_result=expected_df,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "ok"
        assert result["provider"] == "CN1"

    def test_fetch_with_fallback_skips_unavailable(self, registry):
        """测试跳过不可用的数据源"""
        import pandas as pd
        expected_df = pd.DataFrame({"close": [500]})

        registry.register(MockCNProvider(
            name="Unavailable", priority=1, available=False,
            fetch_daily_result="should_not_use",
        ))
        registry.register(MockCNProvider(
            name="Available", priority=10, available=True,
            fetch_daily_result=expected_df,
        ))

        result = registry.fetch_with_fallback(
            code="000001", market="CN", fetch_type="daily",
        )

        assert result["status"] == "ok"
        assert result["provider"] == "Available"


class TestProviderRepr:
    """测试 __repr__ 方法"""

    def test_repr(self):
        provider = MockCNProvider(name="Test", priority=42)
        r = repr(provider)
        assert "Test" in r
        assert "42" in r
        assert "CN" in r


class TestDataProviderPluginInterface:
    """测试抽象接口"""

    def test_cannot_instantiate_abstract(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            DataProviderPlugin()  # Missing abstract methods

    def test_concrete_subclass_instantiates(self):
        """测试具体子类可以实例化"""
        provider = MockCNProvider(name="Valid")
        assert provider.name == "Valid"
        assert provider.priority == 10
        assert provider.market == "CN"
        assert provider.is_available() is True

    def test_fetch_realtime_default_none(self):
        """测试默认 fetch_realtime 返回 None"""
        provider = MockCNProvider(name="Test")
        assert provider.fetch_realtime("000001") is None

    def test_fetch_financials_default_none(self):
        """测试默认 fetch_financials 返回 None"""
        provider = MockCNProvider(name="Test")
        assert provider.fetch_financials("000001") is None
