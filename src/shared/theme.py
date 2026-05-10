"""Theme constants for dark/light mode."""
from typing import Dict
from src.config import get_config

DARK_THEME = {
    "bg": "#1e1e1e",
    "bg_card": "#2d2d2d",
    "bg_input": "#3c3c3c",
    "fg": "#e0e0e0",
    "fg_secondary": "#a0a0a0",
    "accent": "#4CAF50",
    "danger": "#F44336",
    "warning": "#FFC107",
    "border": "#404040",
    "up": "#4CAF50",
    "down": "#F44336",
    "neutral": "#9E9E9E",
}

LIGHT_THEME = {
    "bg": "#ffffff",
    "bg_card": "#f5f5f5",
    "bg_input": "#e8e8e8",
    "fg": "#1e1e1e",
    "fg_secondary": "#666666",
    "accent": "#2E7D32",
    "danger": "#C62828",
    "warning": "#F57F17",
    "border": "#d0d0d0",
    "up": "#2E7D32",
    "down": "#C62828",
    "neutral": "#757575",
}


def get_theme(theme_name: str = "dark") -> Dict[str, str]:
    """Get theme dict by name. Returns DARK_THEME if name invalid."""
    if theme_name == "light":
        return LIGHT_THEME
    return DARK_THEME


def get_current_theme() -> Dict[str, str]:
    """Get theme based on current config."""
    return get_theme(get_config().theme)
