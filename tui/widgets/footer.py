"""Footer bar widget showing shortcuts, notifications, last update time."""
from textual.widgets import Static
from tui.styles.theme import BG_CARD, FG_SECONDARY
from tui.styles.theme import LIGHT_BG, LIGHT_FG, LIGHT_CARD
from src.shared.market_status import get_market_statuses

class Footer(Static):
    """Bottom footer bar."""
    def __init__(self, last_update: str = "---", demo_mode: bool = False):
        super().__init__()
        self._last_update = last_update
        self._market_status = ""
        self._theme = "dark"
        self._demo_mode = demo_mode

    def set_last_update(self, ts: str):
        self._last_update = ts
        self._update_display()

    def set_market_status(self):
        """Update market status indicators from market_status module."""
        statuses = get_market_statuses()
        parts = []
        for market in ["A股", "港股", "美股"]:
            info = statuses[market]
            parts.append(f"{info['emoji']} {market}")
        self._market_status = "  ".join(parts)
        self._update_display()

    def _update_display(self):
        demo_label = "  [演示模式]" if self._demo_mode else ""
        self.update(f"  {self._market_status}  |  最后更新: {self._last_update}{demo_label}  ")

    def apply_theme(self, theme: str):
        """热切换主题"""
        self._theme = theme
        if theme == "light":
            self.styles.background = LIGHT_CARD
            self.styles.color = LIGHT_FG
        else:
            self.styles.background = BG_CARD
            self.styles.color = FG_SECONDARY

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = BG_CARD
        self.styles.color = FG_SECONDARY
        self.set_market_status()
