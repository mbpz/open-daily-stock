"""Footer bar widget showing shortcuts, notifications, last update time."""
from textual.widgets import Static
from tui.styles.theme import BG_CARD, FG_SECONDARY

class Footer(Static):
    """Bottom footer bar."""
    def __init__(self, last_update: str = "---"):
        super().__init__()
        self._last_update = last_update

    def set_last_update(self, ts: str):
        self._last_update = ts
        self.update(f"  ↑↓:移动  Enter:确认  ←:返回  q:退出    最后更新: {self._last_update}  ")

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = BG_CARD
        self.styles.color = FG_SECONDARY
        self.update(f"  ↑↓:移动  Enter:确认  ←:返回  q:退出    最后更新: {self._last_update}  ")
