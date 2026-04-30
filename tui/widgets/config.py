"""Config module for editing settings."""
from textual.widgets import Static, Input
from src.config import get_config

class ConfigView(Static):
    def __init__(self):
        super().__init__()
        self._config = get_config()

    def compose(self):
        stock_list = ",".join(self._config.stock_list)
        yield Static("  自选股列表:", id="label")
        yield Input(value=stock_list, id="stock-list-input")
        yield Static("", id="save-status")
        yield Static("  按 Enter 保存更改", id="hint")

    def on_input_submitted(self, event):
        if event.input.id == "stock-list-input":
            new_list = [s.strip() for s in event.value.split(",") if s.strip()]
            self._config.stock_list = new_list
            self.query_one("#save-status").update("  配置已保存")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
