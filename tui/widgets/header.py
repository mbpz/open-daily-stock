"""Header bar widget showing title, time, connection status."""
from textual.widgets import Static
from datetime import datetime, timezone, timedelta
from tui.styles.theme import BG_DARK, FG_PRIMARY, ACCENT_BLUE

class Header(Static):
    """Top header bar."""
    def on_mount(self):
        self.styles.height = 1
        self.styles.background = ACCENT_BLUE
        self.styles.color = FG_PRIMARY
        self._update_time()

    def _update_time(self):
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M")
        self.update(f"  Stock Analysis TUI    {now}    ● 在线  ")
