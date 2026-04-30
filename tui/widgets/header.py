"""Header bar widget showing title, time, connection status."""
from textual.widgets import Static
from datetime import datetime, timezone, timedelta

class Header(Static):
    """Top header bar."""
    def __init__(self):
        super().__init__()
        self.update(self._render())

    def _render(self) -> str:
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M")
        return f"  Stock Analysis TUI    {now}    ● 在线  "

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#0f4c75"
        self.styles.color = "#e8e8e8"
