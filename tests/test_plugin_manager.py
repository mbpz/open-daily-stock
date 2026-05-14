"""Tests for P7-4 PluginManager: registration, discovery, listing."""
import pytest
from src.plugin_manager import PluginManager, PluginInfo, get_plugin_manager, list_all_plugins


@pytest.fixture(autouse=True)
def reset_plugin_manager():
    """Reset singleton state between tests."""
    PluginManager._instance = None
    yield
    PluginManager._instance = None


class TestPluginInfo:
    def test_default_values(self):
        info = PluginInfo(name="test", domain="data_provider")
        assert info.name == "test"
        assert info.domain == "data_provider"
        assert info.available is True
        assert info.priority == 50

    def test_to_dict(self):
        info = PluginInfo(
            name="test", domain="ai", display_name="Test",
            version="1.0", description="desc", priority=10,
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["domain"] == "ai"
        assert d["priority"] == 10


class TestPluginManager:
    def test_singleton(self):
        pm1 = PluginManager()
        pm2 = PluginManager()
        assert pm1 is pm2

    def test_register(self):
        pm = PluginManager()
        pm.unregister("data_provider", "custom_test")  # Clean up

        class MockFetcher:
            name = "custom_test"
            display_name = "Custom Test Fetcher"
            version = "0.1"
            available = True
            priority = 5

        name = pm.register(MockFetcher(), "data_provider")
        assert name == "custom_test"
        info = pm.list_plugins("data_provider")
        assert any(p.name == "custom_test" for p in info)

        pm.unregister("data_provider", "custom_test")

    def test_register_invalid_domain(self):
        pm = PluginManager()
        with pytest.raises(ValueError, match="Invalid domain"):
            pm.register(object(), "invalid_domain")

    def test_unregister_nonexistent(self):
        pm = PluginManager()
        assert pm.unregister("data_provider", "nonexistent_xyz") is False

    def test_list_domains(self):
        pm = PluginManager()
        domains = pm.list_domains()
        assert "data_provider" in domains
        assert "notify" in domains
        assert "ai" in domains
        assert "strategy" in domains
        assert len(domains) == 4

    def test_count(self):
        pm = PluginManager()
        total = pm.count()
        assert total > 0

    def test_count_by_domain(self):
        pm = PluginManager()
        strategy_count = pm.count("strategy")
        assert strategy_count > 0

    def test_get_domain_plugins(self):
        pm = PluginManager()
        strategies = pm.get_domain_plugins("strategy")
        assert len(strategies) > 0
        assert isinstance(strategies, dict)

    def test_get_plugin(self):
        pm = PluginManager()
        # Built-in should be discoverable
        plugin = pm.get_plugin("strategy", "ma_cross")
        assert plugin is not None


class TestBuiltinDiscovery:
    def test_data_providers_discovered(self):
        pm = PluginManager()
        providers = pm.list_plugins("data_provider")
        names = [p.name for p in providers]
        assert "akshare" in names or "efinance" in names

    def test_strategies_discovered(self):
        pm = PluginManager()
        strategies = pm.list_plugins("strategy")
        names = [p.name for p in strategies]
        for expected in ["ma_cross", "rsi_strategy", "macd_strategy"]:
            assert expected in names, f"{expected} not discovered"

    def test_ai_provider_discovered(self):
        pm = PluginManager()
        ai_plugins = pm.list_plugins("ai")
        assert len(ai_plugins) >= 1


class TestConvenience:
    def test_get_plugin_manager(self):
        pm = get_plugin_manager()
        assert isinstance(pm, PluginManager)

    def test_list_all_plugins(self):
        plugins = list_all_plugins()
        assert len(plugins) > 0
        for p in plugins:
            assert "name" in p
            assert "domain" in p
            assert "available" in p
