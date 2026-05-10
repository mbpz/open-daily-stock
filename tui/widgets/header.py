"""Header bar widget showing title, time, connection status, demo mode indicator."""
from textual.widgets import Static
from datetime import datetime, timezone, timedelta
from tui.styles.theme import BG_DARK, FG_PRIMARY, ACCENT_BLUE
from tui.styles.theme import LIGHT_BG, LIGHT_FG, LIGHT_ACCENT
from src.config import get_config


class Header(Static):
    """Top header bar with demo mode indicator."""

    def __init__(self):
        super().__init__()
        self._theme = "dark"

    def on_mount(self):
        self.styles.height = 1
        self._apply_colors()
        self._update_time()

    def _apply_colors(self):
        if self._theme == "light":
            self.styles.background = LIGHT_ACCENT
            self.styles.color = LIGHT_FG
        else:
            self.styles.background = ACCENT_BLUE
            self.styles.color = FG_PRIMARY

    def apply_theme(self, theme: str):
        """热切换主题"""
        self._theme = theme
        self._apply_colors()

    def _update_time(self):
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M")

        # Check demo mode
        config = get_config()
        if config.is_demo_mode():
            demo_badge = " [演示模式] "
            self.update(f"  Stock Analysis TUI  {demo_badge}  {now}    ● 在线  ")
        else:
            self.update(f"  Stock Analysis TUI    {now}    ● 在线  ")
