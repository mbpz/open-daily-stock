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
        yield Static("", id="verdict-area")
        yield Static("", id="sentiment-bar")
        yield Static("", id="catalysts-area")
        yield Static("", id="risks-area")
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
        """Set plain text result (for errors)"""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")
        # Clear structured display
        self.query_one("#verdict-area", Static).update("")
        self.query_one("#sentiment-bar", Static).update("")
        self.query_one("#catalysts-area", Static).update("")
        self.query_one("#risks-area", Static).update("")
        self.query_one("#result-area", Static).update(text)

    def set_structured_result(self, verdict: str, verdict_color: str, score: int,
                               catalysts: list, risks: list, details: str):
        """Set structured analysis result with verdict badge and sentiment bar"""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")

        # Verdict badge
        verdict_el = self.query_one("#verdict-area", Static)
        verdict_el.update(f"\n  ┌{'─' * 20}┐")
        verdict_el.update(f"  │ {verdict:^18} │")
        verdict_el.update(f"  └{'─' * 20}┘\n")

        # Sentiment bar (ANSI colored)
        bar_width = int(score / 5)  # 0-20 blocks for 0-100 score
        if score >= 60:
            bar_color = "\033[92m"  # green
        elif score >= 40:
            bar_color = "\033[93m"  # yellow
        else:
            bar_color = "\033[91m"  # red
        reset = "\033[0m"
        bar = f"[{bar_color}{'█' * bar_width}{reset}{'░' * (20 - bar_width)}] {score}/100"
        self.query_one("#sentiment-bar", Static).update(f"  {bar}")

        # Catalysts
        catalysts_el = self.query_one("#catalysts-area", Static)
        if catalysts:
            cat_text = "  📈 " + _("看涨因素") + ":\n    " + "\n    ".join(catalysts[:5])
        else:
            cat_text = "  📈 " + _("看涨因素") + ": " + _("暂无")
        catalysts_el.update(cat_text)

        # Risks
        risks_el = self.query_one("#risks-area", Static)
        if risks:
            risk_text = "  📉 " + _("风险因素") + ":\n    " + "\n    ".join(risks[:5])
        else:
            risk_text = "  📉 " + _("风险因素") + ": " + _("暂无")
        risks_el.update(risk_text)

        # Details in result area
        self.query_one("#result-area", Static).update(details)

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)