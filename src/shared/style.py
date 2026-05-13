"""Style constants and formatting functions shared between TUI and GUI."""

# Colors (hex strings - GUI Flet accept hex)
MARKET_UP_COLOR = "#4CAF50"    # green
MARKET_DOWN_COLOR = "#F44336"  # red
MARKET_NEUTRAL_COLOR = "#9E9E9E"  # grey

# Short alias for spec compliance
NEUTRAL_COLOR = MARKET_NEUTRAL_COLOR

# Arrows for price direction
UP_ARROW = "▲"
DOWN_ARROW = "▼"
NEUTRAL_ARROW = "—"

# GUI colors (Flet int color values)
GUI_COLOR_UP = 0x4CAF50
GUI_COLOR_DOWN = 0xF44336
GUI_COLOR_NEUTRAL = 0x9E9E9E

# Legacy aliases (kept for import compatibility)
TUI_COLOR_UP = "green"
TUI_COLOR_DOWN = "red"
TUI_COLOR_NEUTRAL = "grey"

def format_volume(v: float, code: str = None) -> str:
    """Format volume: A-share/HK use 万/亿, US use M/K.

    Args:
        v: volume value
        code: stock code to determine market type (optional, for A股/港股 vs US differentiation)
    """
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    # Determine market type based on code if provided
    if code is not None:
        if code.startswith('hk') or (len(code) == 6 and code.isdigit() and not code.startswith('9')):
            # A股/港股
            if v >= 1e8:
                return f"{v/1e8:.2f}亿"
            if v >= 1e4:
                return f"{v/1e4:.2f}万"
            return f"{v:.0f}"
        else:
            # US stocks
            if v >= 1e9:
                return f"{v/1e9:.2f}B"
            if v >= 1e6:
                return f"{v/1e6:.2f}M"
            if v >= 1e3:
                return f"{v/1e3:.2f}K"
            return f"{v:.0f}"
    # Fallback: use simpler formatting
    if v >= 1e8:
        return f"{v/1e8:.2f}亿"
    if v >= 1e4:
        return f"{v/1e4:.2f}万"
    return f"{v:.0f}"

def format_market_cap(v: float, market: str = "CN") -> str:
    """Format market cap in CNY (亿元) or USD."""
    if v is None:
        return "—"
    if market == "US":
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.2f}B"
        return f"${v/1e6:.2f}M"
    # CNY (亿元)
    if v >= 1e8:
        return f"{v/1e8:.2f}亿"
    return f"{v/1e4:.2f}万"

def format_cny(v: float) -> str:
    """Format CNY currency."""
    if v is None:
        return "—"
    return f"¥{v:,.2f}"

def format_pct(p: float) -> str:
    """Format percentage with arrow."""
    if p is None:
        return "—%—"
    if p > 0:
        return f"+{p:.2f}%{UP_ARROW}"
    if p < 0:
        return f"{p:.2f}%{DOWN_ARROW}"
    return f"{p:.2f}%{NEUTRAL_ARROW}"

def format_hkd(v: float) -> str:
    """Format HKD currency."""
    if v is None:
        return "—"
    return f"HK${v:,.2f}"

def format_usd(v: float) -> str:
    """Format USD currency."""
    if v is None:
        return "—"
    return f"${v:,.2f}"