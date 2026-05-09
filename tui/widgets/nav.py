"""Navigation tabs for module switching."""
from textual.widgets import Static
from tui.styles.theme import BG_DARK, FG_SECONDARY
from tui.styles.theme import LIGHT_BG, LIGHT_FG, LIGHT_CARD

class Nav(Static):
    """Module navigation tabs."""
    MODULES = ["Markets", "Tasks", "Analyze", "Config", "Logs"]
    def __init__(self, active: int = 0):
        super().__init__()
        self._active = active
        self._theme = "dark"

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

    def apply_theme(self, theme: str):
        """热切换主题"""
        self._theme = theme
        if theme == "light":
            self.styles.background = LIGHT_CARD
            self.styles.color = LIGHT_FG
        else:
            self.styles.background = BG_DARK
            self.styles.color = FG_SECONDARY

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = BG_DARK
        self.styles.color = FG_SECONDARY
        self._update_display()
