"""P7-4: Unified Plugin Manager for open-daily-stock.

Manages plugins across all extension domains:
  - data_provider: Stock data fetchers (AkShare, YFinance, etc.)
  - notify: Notification channels (WeChat, Feishu, Telegram, etc.)
  - ai: AI model providers (DeepSeek, OpenAI-compatible)
  - strategy: Trading strategies (builtin + community)

Usage:
    pm = get_plugin_manager()
    pm.register(MyCustomFetcher(), domain="data_provider")
    fetchers = pm.list_plugins("data_provider")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plugin base
# ---------------------------------------------------------------------------

@dataclass
class PluginInfo:
    """Metadata about a registered plugin."""
    name: str
    domain: str  # "data_provider" | "notify" | "ai" | "strategy"
    display_name: str = ""
    version: str = ""
    description: str = ""
    available: bool = True
    priority: int = 50
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "available": self.available,
            "priority": self.priority,
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# Plugin Manager
# ---------------------------------------------------------------------------

class PluginManager:
    """Central registry for all plugin types.

    Domains:
      - data_provider: Stock data fetchers
      - notify: Notification channels
      - ai: AI model providers
      - strategy: Trading strategies
    """

    _instance: Optional["PluginManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._plugins: Dict[str, Dict[str, Any]] = {
            "data_provider": {},
            "notify": {},
            "ai": {},
            "strategy": {},
        }
        self._infos: Dict[str, Dict[str, PluginInfo]] = {
            "data_provider": {},
            "notify": {},
            "ai": {},
            "strategy": {},
        }
        self._initialized = True

        # Auto-discover built-in plugins
        self._discover_builtins()

    # ------------------------------------------------------------------
    # Register / Unregister
    # ------------------------------------------------------------------

    def register(
        self,
        instance: Any,
        domain: str,
        name: Optional[str] = None,
        info: Optional[PluginInfo] = None,
    ) -> str:
        """Register a plugin instance.

        Args:
            instance: The plugin object (fetcher, notifier, analyzer, strategy class).
            domain: Plugin domain.
            name: Plugin name. Auto-detected from instance if not provided.
            info: Optional PluginInfo metadata.

        Returns:
            Plugin name used for registration.

        Raises:
            ValueError: if domain is invalid.
        """
        if domain not in self._plugins:
            raise ValueError(f"Invalid domain: {domain}. Must be one of {list(self._plugins.keys())}")

        if name is None:
            name = getattr(instance, "name", instance.__class__.__name__)

        self._plugins[domain][name] = instance

        if info is None:
            info = PluginInfo(
                name=name,
                domain=domain,
                display_name=getattr(instance, "display_name", name),
                version=getattr(instance, "version", ""),
                description=getattr(instance, "description", ""),
                available=self._check_available(instance),
                priority=getattr(instance, "priority", 50),
            )
        self._infos[domain][name] = info

        logger.debug(f"Plugin registered: [{domain}] {name}")
        return name

    def unregister(self, domain: str, name: str) -> bool:
        """Unregister a plugin. Returns True if found and removed."""
        if domain not in self._plugins:
            return False
        removed = self._plugins[domain].pop(name, None) is not None
        self._infos[domain].pop(name, None)
        if removed:
            logger.debug(f"Plugin unregistered: [{domain}] {name}")
        return removed

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_plugin(self, domain: str, name: str) -> Optional[Any]:
        """Get a plugin instance by domain and name."""
        return self._plugins.get(domain, {}).get(name)

    def list_plugins(self, domain: Optional[str] = None) -> List[PluginInfo]:
        """List all plugins, optionally filtered by domain."""
        result = []
        domains = [domain] if domain else list(self._plugins.keys())
        for d in domains:
            if d in self._infos:
                for info in self._infos[d].values():
                    # Refresh availability
                    instance = self._plugins[d].get(info.name)
                    if instance:
                        info.available = self._check_available(instance)
                result.extend(self._infos[d].values())
        return sorted(result, key=lambda x: x.priority)

    def list_domains(self) -> List[str]:
        """Return sorted list of registered domains."""
        return sorted(self._plugins.keys())

    def get_domain_plugins(self, domain: str) -> Dict[str, Any]:
        """Get all plugin instances in a domain as {name: instance}."""
        return dict(self._plugins.get(domain, {}))

    def count(self, domain: Optional[str] = None) -> int:
        if domain:
            return len(self._plugins.get(domain, {}))
        return sum(len(v) for v in self._plugins.values())

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    @staticmethod
    def _check_available(instance: Any) -> bool:
        """Check if a plugin instance is available (has required config/API keys)."""
        if hasattr(instance, "is_available"):
            try:
                return instance.is_available()
            except Exception:
                return True
        if hasattr(instance, "available"):
            return bool(instance.available)
        return True

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    def _discover_builtins(self) -> None:
        """Auto-discover and register built-in plugins from all domains."""
        self._discover_data_providers()
        self._discover_notifiers()
        self._discover_ai_providers()
        self._discover_strategies()

    def _discover_data_providers(self) -> None:
        """Register built-in data providers."""
        try:
            from data_provider.akshare_fetcher import AkshareFetcher
            from data_provider.yfinance_fetcher import YfinanceFetcher
            from data_provider.efinance_fetcher import EfinanceFetcher
            from data_provider.baostock_fetcher import BaostockFetcher

            providers = [
                (EfinanceFetcher(), "efinance", 0),
                (AkshareFetcher(), "akshare", 1),
                (BaostockFetcher(), "baostock", 3),
                (YfinanceFetcher(), "yfinance", 4),
            ]
            for instance, name, priority in providers:
                instance.priority = priority
                self.register(instance, "data_provider", name=name)
        except ImportError as e:
            logger.debug(f"Data provider discovery skipped: {e}")

    def _discover_notifiers(self) -> None:
        """Register notification channel plugins."""
        try:
            from src.notify.channels import ALL_CHANNELS
            for name, cls in ALL_CHANNELS.items():
                try:
                    instance = cls()
                    self.register(instance, "notify", name=name)
                except Exception as e:
                    logger.debug(f"Notifier {name} unavailable: {e}")
        except ImportError:
            logger.debug("Notification channels not found")

    def _discover_ai_providers(self) -> None:
        """Register AI model providers."""
        try:
            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            self.register(analyzer, "ai", name="deepseek", info=PluginInfo(
                name="deepseek",
                domain="ai",
                display_name="DeepSeek (OpenAI Compatible)",
                version="v1",
                description="DeepSeek AI via OpenAI-compatible API",
                available=analyzer.is_available(),
                priority=10,
            ))
        except ImportError as e:
            logger.debug(f"AI provider discovery skipped: {e}")

    def _discover_strategies(self) -> None:
        """Register built-in strategy plugins."""
        try:
            from src.strategies.builtin import BUILTIN_STRATEGIES
            for cls in BUILTIN_STRATEGIES:
                instance = cls()
                self.register(instance, "strategy", name=instance.name)
        except ImportError as e:
            logger.debug(f"Strategy discovery skipped: {e}")


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

def get_plugin_manager() -> PluginManager:
    """Return the singleton PluginManager instance."""
    return PluginManager()


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def list_all_plugins() -> List[Dict[str, Any]]:
    """List all registered plugins as dicts (for API responses)."""
    pm = get_plugin_manager()
    return [info.to_dict() for info in pm.list_plugins()]
