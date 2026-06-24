"""config handlers — keybindings / theme / language / config get+update。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.config import get_config

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# 写时可持久化的 config 项：(attr_name, save_to_json_or_env)
_WRITABLE_CONFIG: Dict[str, tuple] = {
    "theme": ("theme", True),
    "language": ("language", True),
    "schedule_time": ("schedule_time", False),
    "report_type": ("report_type", False),
    "single_stock_notify": ("single_stock_notify", False),
    "mode": ("mode", True),
    "analysis_delay": ("analysis_delay", False),
    "max_workers": ("max_workers", False),
    "debug": ("debug", False),
    "schedule_enabled": ("schedule_enabled", False),
    "market_review_enabled": ("market_review_enabled", False),
    "indicators": ("indicators", True),
    "chart_draw_support_resistance": ("chart_draw_support_resistance", True),
    "chart_draw_fibonacci": ("chart_draw_fibonacci", True),
    "schedule_refresh_enabled": ("schedule_refresh_enabled", False),
    "schedule_refresh_time": ("schedule_refresh_time", False),
}


# ─── Handlers ──────────────────────────────────────────────────


def get_keybindings(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """返回指定 section 的 keybindings 配置。"""
    from src.shared.keybindings import get_all_keybindings
    section = req.get("section", "global")
    return {"status": "ok", "data": get_all_keybindings(section)}


def get_theme(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get current theme and color palette."""
    from src.shared.theme import get_current_theme
    config = get_config()
    return {
        "status": "ok",
        "data": {
            "theme": config.theme,
            "colors": get_current_theme(),
        },
    }


def set_theme(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Set theme at runtime ('dark' or 'light')."""
    theme_name = req.get("theme", "dark")
    if theme_name not in ("dark", "light"):
        return {"status": "error", "message": "theme must be 'dark' or 'light'"}
    config = get_config()
    config.theme = theme_name
    config.save_json_config({"theme": theme_name})
    return {"status": "ok", "message": f"主题已切换为 {theme_name}", "theme": theme_name}


def get_languages(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get available languages and current language."""
    from src.shared.i18n import get_available_languages, get_current_lang
    return {
        "status": "ok",
        "data": {
            "available": get_available_languages(),
            "current": get_current_lang(),
        },
    }


def set_language(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Set current language at runtime."""
    from src.shared.i18n import TRANSLATIONS, get_available_languages
    lang = req.get("language", "zh")
    if lang not in TRANSLATIONS:
        return {"status": "error", "message": f"不支持的语言: {lang}"}
    config = get_config()
    config.language = lang
    config.save_json_config({"language": lang})
    return {"status": "ok", "message": f"语言已切换为 {get_available_languages()[lang]}"}


def get_config_(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get current application configuration.

    If a specific 'key' is provided, returns only that config value.
    Otherwise returns all UI-serializable config fields.
    """
    config = get_config()
    key = req.get("key")

    config_data = {
        "theme": config.theme,
        "language": config.language,
        "schedule_enabled": config.schedule_enabled,
        "schedule_time": config.schedule_time,
        "market_review_enabled": config.market_review_enabled,
        "report_type": config.report_type,
        "single_stock_notify": config.single_stock_notify,
        "analysis_delay": config.analysis_delay,
        "max_workers": config.max_workers,
        "debug": config.debug,
        "mode": config.mode,
        "indicators": config.indicators,
        "chart_draw_support_resistance": config.chart_draw_support_resistance,
        "chart_draw_fibonacci": config.chart_draw_fibonacci,
        "keybindings": config.keybindings,
        "schedule_refresh_enabled": config.schedule_refresh_enabled,
        "schedule_refresh_time": config.schedule_refresh_time,
        "data_provider_plugins": config.data_provider_plugins,
        "stock_list": config.stock_list,
        "log_dir": config.log_dir,
        "log_level": config.log_level,
    }

    if key:
        if key not in config_data:
            return {"status": "error", "message": f"Unknown config key: {key}"}
        return {"status": "ok", "data": {key: config_data[key]}}

    return {"status": "ok", "data": config_data}


def update_config(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Update application configuration at runtime."""
    config = get_config()
    key = req.get("key")
    value = req.get("value")

    if not key:
        return {"status": "error", "message": "缺少 key 参数"}
    if value is None:
        return {"status": "error", "message": "缺少 value 参数"}

    if key not in _WRITABLE_CONFIG:
        return {"status": "error", "message": f"不支持的配置项: {key}"}

    attr_name, save_to_json = _WRITABLE_CONFIG[key]

    # Validate specific keys
    if key == "theme" and value not in ("dark", "light"):
        return {"status": "error", "message": "theme 必须是 'dark' 或 'light'"}

    if key == "language":
        from src.shared.i18n import TRANSLATIONS
        if value not in TRANSLATIONS:
            return {"status": "error", "message": f"不支持的语言: {value}"}

    if key == "report_type" and value not in ("simple", "full"):
        return {"status": "error", "message": "report_type 必须是 'simple' 或 'full'"}

    setattr(config, attr_name, value)

    if save_to_json:
        config.save_json_config({key: value})
    else:
        config.save_to_env({key.upper(): str(value)})

    return {"status": "ok", "message": f"配置已更新: {key} = {value}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_keybindings = partial(get_keybindings, service)
    service._actions["get_keybindings"] = "_handle_get_keybindings"

    service._handle_get_theme = partial(get_theme, service)
    service._actions["get_theme"] = "_handle_get_theme"
    service._handle_set_theme = partial(set_theme, service)
    service._actions["set_theme"] = "_handle_set_theme"

    service._handle_get_languages = partial(get_languages, service)
    service._actions["get_languages"] = "_handle_get_languages"
    service._handle_set_language = partial(set_language, service)
    service._actions["set_language"] = "_handle_set_language"

    service._handle_get_config = partial(get_config_, service)
    service._actions["get_config"] = "_handle_get_config"
    service._handle_update_config = partial(update_config, service)
    service._actions["update_config"] = "_handle_update_config"
