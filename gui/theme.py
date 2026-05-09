"""Flet GUI 主题配置 - 支持 dark/light 切换"""

# === Dark Theme (default) ===
DARK = {
    "PRIMARY_COLOR": "#1a1a2e",
    "SECONDARY_COLOR": "#16213e",
    "ACCENT_COLOR": "#0f3460",
    "HIGHLIGHT_COLOR": "#e94560",
    "TEXT_PRIMARY": "#e8e8e8",
    "TEXT_SECONDARY": "#a0a0a0",
    "TEXT_MUTED": "#666666",
    "SUCCESS_COLOR": "#4caf50",
    "ERROR_COLOR": "#f44336",
    "WARNING_COLOR": "#ff9800",
    "DONE_BG": "#1b5e20",
    "CARD_BG": "#16213e",
    "CARD_BORDER": "#0f3460",
}

# === Light Theme ===
LIGHT = {
    "PRIMARY_COLOR": "#f5f5f5",
    "SECONDARY_COLOR": "#ffffff",
    "ACCENT_COLOR": "#e0e0e0",
    "HIGHLIGHT_COLOR": "#2E7D32",
    "TEXT_PRIMARY": "#212121",
    "TEXT_SECONDARY": "#555555",
    "TEXT_MUTED": "#888888",
    "SUCCESS_COLOR": "#2E7D32",
    "ERROR_COLOR": "#C62828",
    "WARNING_COLOR": "#F57F17",
    "DONE_BG": "#c8e6c9",
    "CARD_BG": "#ffffff",
    "CARD_BORDER": "#cccccc",
}

# 当前主题
_current = "dark"
_theme = DARK

# 内部名称集合（不作为颜色导出）
_INTERNAL = frozenset({
    "DARK", "LIGHT", "_current", "_theme", "_INTERNAL",
    "get_theme", "set_theme", "get_current_theme_name",
    "__getattr__",
})


def __getattr__(name: str) -> str:
    """模块级 __getattr__ - 使 `from gui.theme import PRIMARY_COLOR` 返回当前主题值"""
    if name in _INTERNAL:
        raise AttributeError(name)
    if name in _theme:
        return _theme[name]
    raise AttributeError(f"module 'gui.theme' has no attribute '{name}'")


def get_theme() -> dict:
    """获取当前主题颜色字典"""
    return _theme


def set_theme(name: str) -> dict:
    """切换主题（'dark' 或 'light'），返回新主题字典"""
    global _current, _theme
    if name == "light":
        _current = "light"
        _theme = LIGHT
    else:
        _current = "dark"
        _theme = DARK
    return _theme


def get_current_theme_name() -> str:
    """获取当前主题名称"""
    return _current
