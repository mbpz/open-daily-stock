"""DataService handlers 域拆分。

按域拆分为 16 个子模块，每个子模块提供 `register(service: DataService) -> None`
把 `action -> handler` 注入到 `service._actions` dict。

Handler 函数签名：
    def handler(service: DataService, req: Dict[str, Any]) -> Dict[str, Any]

显式参数（不传 self）— 透过 `service` 参数访问实例状态，便于未来脱钩为
独立 service。

迁移计划见 docs/superpowers/plans/2026-06-19-data-service-handler-split.md。
"""
from typing import TYPE_CHECKING

from . import (
    alerts,
    analysis,
    backtest,
    config_handlers as config,
    core,
    factors,
    financials,
    institutional,
    market_review,
    markets,
    plugins,
    portfolio,
    screen,
    search,
    sim,
    strategies,
)

if TYPE_CHECKING:
    from src.data_service import DataService


# 所有域的 register 顺序（先注册的可被后注册的覆盖——故意让旧 _actions 优先）
# 这样新 module 里的实现与旧 DataService 类方法同名也不会冲突：
#   - 同一 action：register() 后写覆盖
#   - 类方法 vs 实例属性：实例属性（由 register 挂上）覆盖类方法
ALL_REGISTRARS = (
    core,
    config,
    plugins,
    alerts,
    portfolio,
    sim,
    institutional,
    markets,
    backtest,
    financials,
    screen,
    strategies,
    search,
    factors,
    market_review,
    analysis,
)


def register_all(service: "DataService") -> None:
    """调用所有域的 register(service)，把 actions 注入到 service._actions dict。

    与 DataService 类内硬编码的 _actions dict 兼容：register 写新 key 时不会
    互相覆盖，因为同名 key 的 _actions value 也指向同一字符串（"_handle_xxx"）；
    真正决定谁运行的是 `getattr(self, "_handle_xxx")` —— 域 module 内通过
    `service._handle_xxx = handler` 挂的实例属性优先于类方法。
    """
    for registrar in ALL_REGISTRARS:
        registrar.register(service)


__all__ = [
    "register_all",
    "alerts",
    "analysis",
    "backtest",
    "config",
    "core",
    "factors",
    "financials",
    "institutional",
    "market_review",
    "markets",
    "plugins",
    "portfolio",
    "screen",
    "search",
    "sim",
    "strategies",
]
