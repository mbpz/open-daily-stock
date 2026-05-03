"""Analyze module for triggering stock analysis."""
from textual.widgets import Static, Input, Button, ProgressBar
from textual.message import Message
from src.i18n import _


class AnalyzeView(Static):
    def __init__(self, on_analyze: callable):
        super().__init__()
        self._on_analyze = on_analyze
        self._progress_bar = None
        self._progress_text = None

    def compose(self):
        yield Static(_("  输入股票代码: "), id="label")
        yield Input(placeholder="600519, 000001, hk00700, AAPL", id="stock-input")
        yield Button(_("开始分析"), id="analyze-btn")
        yield Static("", id="result-area")
        yield ProgressBar(id="progress-bar", show_percentage=False)
        yield Static("", id="progress-text")

    def on_button_pressed(self, event):
        if event.button.id == "analyze-btn":
            stock_code = self.query_one("#stock-input", Input).value.strip()
            if stock_code:
                self._on_analyze(stock_code, self._update_progress)
                self.query_one("#result-area").update(_("分析中...\n"))
                self._show_progress()

    def _show_progress(self):
        """显示进度条"""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = True
        progress_bar.update(progress=0)
        progress_text.update(_("正在获取数据..."))
        self.refresh()

    def _update_progress(self, stage: str, percent: int, message: str):
        """更新进度回调"""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.update(progress=percent / 100.0)
        progress_text.update(message)
        self.refresh()

    def set_result(self, text: str):
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")
        self.query_one("#result-area").update(text)

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
