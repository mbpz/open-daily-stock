"""Navigation tabs for module switching."""
from textual.widgets import Static
from tui.styles.theme import BG_DARK, FG_SECONDARY

class Nav(Static):
    """Module navigation tabs."""
    MODULES = ["Markets", "Tasks", "Analyze", "Config", "Logs"]
    def __init__(self, active: int = 0):
        super().__init__()
        self._active = active

    def set_active(self, idx: int):
        self._active = idx
        self._update_display()

    def _update_display(self):
        parts = []
        for i, m in enumerate(self.MODULES):
            mark = "[" + str(i+1) + "]"
            prefix = ">" if i == self._active else " "
            parts.append(f"{prefix}{mark} {m}")
        self.update("  ".join(parts))

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = BG_DARK
        self.styles.color = FG_SECONDARY
        self._update_display()
