"""Keyboard shortcut configuration support.

Provides helper functions to access configurable keybindings from config.py,
allowing TUI widgets to look up key bindings by section and action name.
"""
from typing import Dict, Optional
from src.config import get_config


def get_keybinding(section: str, action: str) -> Optional[str]:
    """Get configured keybinding for a section/action pair.

    Args:
        section: 'global', 'markets', 'analysis', 'tasks'
        action: action name like 'quit', 'refresh', etc.

    Returns:
        Key string or None if not configured
    """
    config = get_config()
    try:
        return config.keybindings.get(section, {}).get(action)
    except AttributeError:
        return None


def get_all_keybindings(section: str) -> Dict[str, str]:
    """Get all keybindings for a section.

    Args:
        section: 'global', 'markets', 'analysis', 'tasks'

    Returns:
        Dict mapping action names to key strings
    """
    config = get_config()
    try:
        return dict(config.keybindings.get(section, {}))
    except AttributeError:
        return {}
