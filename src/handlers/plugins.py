"""plugins handlers — list_plugins / get_plugin_info / list_providers (P7-4 插件系统)。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def list_plugins(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """List all registered plugins (P7-4)."""
    try:
        from src.plugin_manager import list_all_plugins
        domain = req.get("domain")
        plugins = list_all_plugins()
        if domain:
            plugins = [p for p in plugins if p["domain"] == domain]
        return {"status": "ok", "data": plugins}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_plugin_info(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get plugin details (P7-4)."""
    try:
        from src.plugin_manager import get_plugin_manager
        pm = get_plugin_manager()
        domain = req.get("domain", "")
        name = req.get("name", "")
        plugins = pm.get_domain_plugins(domain)
        info = plugins.get(name)
        return {"status": "ok", "data": str(info)[:500] if info else None}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_providers(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """列出所有已注册的数据源插件"""
    from src.data_provider.plugin import ProviderRegistry
    market = req.get("market", "ALL")
    registry = ProviderRegistry.get_instance()
    providers = registry.list_providers(market)
    return {
        "status": "ok",
        "data": [
            {
                "name": p.name,
                "priority": p.priority,
                "market": p.market,
                "available": p.is_available(),
            }
            for p in providers
        ],
    }


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_list_plugins = partial(list_plugins, service)
    service._actions["list_plugins"] = "_handle_list_plugins"

    service._handle_get_plugin_info = partial(get_plugin_info, service)
    service._actions["get_plugin_info"] = "_handle_get_plugin_info"

    service._handle_list_providers = partial(list_providers, service)
    service._actions["list_providers"] = "_handle_list_providers"
