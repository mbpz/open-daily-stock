"""Navigation tabs for module switching."""
from textual.widgets import Static

class Nav(Static):
    """Module navigation tabs."""
    MODULES = ["Markets", "Tasks", "Analyze", "Config", "Logs"]
    def __init__(self, active: int = 0):
        super().__init__()
        self._active = active
        self.update(self._render())

    def _render(self) -> str:
        parts = []
        for i, m in enumerate(self.MODULES):
            mark = "[" + str(i+1) + "]"
            prefix = ">" if i == self._active else " "
            parts.append(f"{prefix}{mark} {m}")
        return "  ".join(parts)

    def set_active(self, idx: int):
        self._active = idx
        self.update(self._render())

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#1a1a2e"
        self.styles.color = "#a0a0a0"
