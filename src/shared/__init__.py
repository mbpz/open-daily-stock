"""Shared components for TUI/GUI code reuse."""
from .style import (
    MARKET_UP_COLOR, MARKET_DOWN_COLOR, MARKET_NEUTRAL_COLOR, NEUTRAL_COLOR,
    UP_ARROW, DOWN_ARROW, NEUTRAL_ARROW,
    format_volume, format_market_cap, format_cny, format_pct,
    TUI_COLOR_UP, TUI_COLOR_DOWN, TUI_COLOR_NEUTRAL,
    GUI_COLOR_UP, GUI_COLOR_DOWN, GUI_COLOR_NEUTRAL,
)
from .market_status import get_market_statuses, MarketStatus
from .indicators import (
    calculate_rsi, calculate_macd, calculate_kdj,
    calculate_wr, calculate_obv, calculate_bollinger_bands,
)
from .sparkline import (
    SPARKLINE_CHARS,
    generate_sparkline,
    generate_sparkline_with_color,
    generate_change_sparkline,
)
from .keybindings import get_keybinding, get_all_keybindings

__all__ = [
    "MARKET_UP_COLOR", "MARKET_DOWN_COLOR", "MARKET_NEUTRAL_COLOR", "NEUTRAL_COLOR",
    "UP_ARROW", "DOWN_ARROW", "NEUTRAL_ARROW",
    "format_volume", "format_market_cap", "format_cny", "format_pct",
    "TUI_COLOR_UP", "TUI_COLOR_DOWN", "TUI_COLOR_NEUTRAL",
    "GUI_COLOR_UP", "GUI_COLOR_DOWN", "GUI_COLOR_NEUTRAL",
    "get_market_statuses", "MarketStatus",
    "calculate_rsi", "calculate_macd", "calculate_kdj",
    "calculate_wr", "calculate_obv", "calculate_bollinger_bands",
    "SPARKLINE_CHARS",
    "generate_sparkline",
    "generate_sparkline_with_color",
    "generate_change_sparkline",
    "get_keybinding", "get_all_keybindings",
]