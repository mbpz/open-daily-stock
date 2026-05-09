# -*- coding: utf-8 -*-
"""
===================================
数据源插件架构 - Plugin Registry
===================================

设计模式: 注册模式 (Registry Pattern)
- DataProviderPlugin: 抽象基类，定义插件接口
- ProviderRegistry: 单例注册中心，管理所有数据源插件

支持:
1. 优先级排序（低优先级的先尝试）
2. 按市场过滤
3. 自动故障切换（fetch_with_fallback）
4. 外部插件动态加载

优先级编号约定:
  内置: akshare=10, yfinance=20, efinance=30
  外部: wind=1, dongcai=5 (优先级低于内置)
  自定义公开源: 50+
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


class DataProviderPlugin(ABC):
    """数据源插件抽象基类

    所有数据源（内置或外部）都应实现此接口。
    外部插件（如 Wind、东方财富）只需继承此类并实现抽象方法，
    然后通过配置 data_provider_plugins 自动加载。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """唯一的数据源名称"""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级（数字越小越先尝试）

        内置数据源:
          akshare=10, yfinance=20, efinance=30
        外部插件建议:
          1-9: 付费/高级数据源 (Wind, 东方财富 Data)
          50+: 自定义公开数据源
        """
        ...

    @property
    @abstractmethod
    def market(self) -> str:
        """支持的市场: 'CN', 'HK', 'US', 或 'ALL'"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用（如 API key 已配置、网络可达）"""
        ...

    @abstractmethod
    def fetch_daily(self, code: str, days: int = 1):
        """获取日线 OHLCV 数据

        Args:
            code: 股票代码
            days: 获取天数

        Returns:
            pd.DataFrame 或 None
        """
        ...

    def fetch_realtime(self, code: str) -> Optional[Dict]:
        """获取实时行情数据。

        重写此方法以支持实时行情获取。默认返回 None。

        Args:
            code: 股票代码

        Returns:
            实时行情 dict 或 None
        """
        return None

    def fetch_financials(self, code: str) -> Optional[Dict]:
        """获取财务数据。

        重写此方法以支持财务数据获取。默认返回 None。

        Args:
            code: 股票代码

        Returns:
            财务数据 dict 或 None
        """
        return None

    def __repr__(self):
        return f"<{self.name} pri={self.priority} market={self.market}>"


class ProviderRegistry:
    """数据源插件注册中心（单例）

    管理所有已注册的数据源插件，支持:
    - 注册/注销插件
    - 按优先级排序获取
    - 按市场过滤
    - 自动故障切换

    Usage::

        registry = ProviderRegistry.get_instance()
        registry.register(MyProvider())
        providers = registry.list_providers(market="CN")
    """

    _instance: Optional["ProviderRegistry"] = None
    _providers: Dict[str, DataProviderPlugin] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ProviderRegistry":
        """获取注册中心单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: DataProviderPlugin):
        """注册一个数据源插件"""
        if provider.name in self._providers:
            logger.warning(f"Provider {provider.name} already registered, replacing")
        self._providers[provider.name] = provider
        logger.info(f"Registered provider: {provider.name} (priority={provider.priority})")

    def unregister(self, name: str):
        """注销指定名称的数据源"""
        self._providers.pop(name, None)

    def get_provider(self, name: str) -> Optional[DataProviderPlugin]:
        """按名称获取数据源"""
        return self._providers.get(name)

    def list_providers(self, market: Optional[str] = None) -> List[DataProviderPlugin]:
        """列出所有已注册的数据源，按优先级排序（低优先级的在前）

        Args:
            market: 按市场过滤（'CN', 'HK', 'US'），None 表示不过滤

        Returns:
            按优先级升序排列的插件列表
        """
        providers = list(self._providers.values())
        if market:
            providers = [p for p in providers if p.market in (market, "ALL")]
        return sorted(providers, key=lambda p: p.priority)

    def get_available_providers(self, market: Optional[str] = None) -> List[DataProviderPlugin]:
        """列出当前可用的数据源（is_available() 返回 True）

        Args:
            market: 按市场过滤

        Returns:
            可用的插件列表，按优先级排序
        """
        return [p for p in self.list_providers(market) if p.is_available()]

    def fetch_with_fallback(self, code: str, market: str = "CN",
                            fetch_type: str = "daily", **kwargs) -> Dict:
        """按优先级依次尝试所有可用数据源，返回第一个成功的结果。

        Args:
            code: 股票代码
            market: 市场类型
            fetch_type: 数据获取类型: 'daily', 'realtime', 'financials'
            **kwargs: 传递给 fetch 方法的额外参数

        Returns:
            {"status": "ok", "provider": <name>, "data": <result>} 或
            {"status": "error", "errors": [<error messages>]}
        """
        errors = []
        for provider in self.get_available_providers(market):
            try:
                if fetch_type == "daily":
                    result = provider.fetch_daily(code, **kwargs)
                elif fetch_type == "realtime":
                    result = provider.fetch_realtime(code)
                elif fetch_type == "financials":
                    result = provider.fetch_financials(code)
                else:
                    result = None

                if result is not None:
                    return {"status": "ok", "provider": provider.name, "data": result}
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                continue

        return {"status": "error", "errors": errors}

    @classmethod
    def reset(cls):
        """重置注册中心（主要用于测试）"""
        cls._instance = None
        cls._providers = {}
