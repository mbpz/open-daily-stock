"""Footer bar widget showing shortcuts, notifications, last update time."""
from textual.widgets import Static

class Footer(Static):
    """Bottom footer bar."""
    def __init__(self, last_update: str = "---"):
        super().__init__()
        self._last_update = last_update
        self.update(self._render())

    def _render(self) -> str:
        return f"  ↑↓:移动  Enter:确认  ←:返回  q:退出    最后更新: {self._last_update}  "

    def set_last_update(self, ts: str):
        self._last_update = ts
        self.update(self._render())

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#16213e"
        self.styles.color = "#a0a0a0"
