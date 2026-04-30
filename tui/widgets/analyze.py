"""Analyze module for triggering stock analysis."""
from textual.widgets import Static, Input, Button
from textual.message import Message

class AnalyzeView(Static):
    def __init__(self, on_analyze: callable):
        super().__init__()
        self._on_analyze = on_analyze

    def compose(self):
        yield Static("  输入股票代码: ", id="label")
        yield Input(placeholder="600519, 000001, hk00700, AAPL", id="stock-input")
        yield Button("开始分析", id="analyze-btn")
        yield Static("", id="result-area")

    def on_button_pressed(self, event):
        if event.button.id == "analyze-btn":
            stock_code = self.query_one("#stock-input", Input).value.strip()
            if stock_code:
                self._on_analyze(stock_code)
                self.query_one("#result-area").update("分析中...\n")

    def set_result(self, text: str):
        self.query_one("#result-area").update(text)

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
