"""Analyze module for triggering stock analysis."""
from textual.widgets import Static, Input, Button, ProgressBar
from textual.message import Message
from src.i18n import _


class AnalyzeView(Static):
    def __init__(self, on_analyze: callable, on_deep_analyze: callable = None):
        super().__init__()
        self._on_analyze = on_analyze
        self._on_deep_analyze = on_deep_analyze
        self._progress_bar = None
        self._progress_text = None
        self._streaming = False
        self._stream_buffer = ""
        self._stream_dot_count = 0
        self._stream_timer = None

    def compose(self):
        yield Static(_("  输入股票代码: "), id="label")
        yield Input(placeholder="600519, 000001, hk00700, AAPL", id="stock-input")
        yield Button(_("开始分析"), id="analyze-btn")
        yield Button(_("深度分析"), id="deep-analyze-btn", classes="deep-btn")
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
        elif event.button.id == "deep-analyze-btn":
            stock_code = self.query_one("#stock-input", Input).value.strip()
            if stock_code and self._on_deep_analyze:
                self._on_deep_analyze(stock_code, self._update_progress)
                self.query_one("#result-area").update(
                    _("深度分析中...\n[1/4] 技术面分析中...\n[2/4] 基本面分析中...\n[3/4] 消息面分析中...\n[4/4] 综合分析中...\n")
                )
                self._show_progress()
                self._is_deep = True

    def action_deep_analyze(self):
        """Ctrl+D: 触发深度分析"""
        stock_code = self.query_one("#stock-input", Input).value.strip()
        if stock_code and self._on_deep_analyze:
            self._on_deep_analyze(stock_code, self._update_progress)
            self.query_one("#result-area").update(
                _("深度分析中...\n[1/4] 技术面分析中...\n[2/4] 基本面分析中...\n[3/4] 消息面分析中...\n[4/4] 综合分析中...\n")
            )
            self._show_progress()
            self._is_deep = True

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

    # ================================================================
    # Streaming display methods (P5-1)
    # ================================================================

    def start_stream(self):
        """Begin a streaming analysis display.

        Clears any previous result and shows a streaming indicator ("...").
        """
        self._streaming = True
        self._stream_buffer = ""
        self._stream_dot_count = 0

        # Clear structured fields
        self.query_one("#verdict-area", Static).update("")
        self.query_one("#sentiment-bar", Static).update("")
        self.query_one("#catalysts-area", Static).update("")
        self.query_one("#risks-area", Static).update("")

        # Show progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.visible = True
        progress_bar.update(progress=0)

        # Show streaming indicator
        progress_text = self.query_one("#progress-text", Static)
        progress_text.update(_("正在流式分析..."))

        # Initialize result area with streaming indicator
        result_area = self.query_one("#result-area", Static)
        result_area.update(_("分析中") + " ...\n")
        self.refresh()

    def append_stream_chunk(self, chunk: str):
        """Append a chunk of streaming text to the result area.

        Args:
            chunk: Partial text from the LLM streaming response
        """
        if not self._streaming:
            self.start_stream()

        self._stream_buffer += chunk

        # Update the animated dots every ~8 chunks
        self._stream_dot_count = (self._stream_dot_count + 1) % 8
        dots = "." * (self._stream_dot_count % 4)

        result_area = self.query_one("#result-area", Static)
        # Show last ~2000 chars of buffer + streaming indicator
        display = self._stream_buffer[-2000:]
        if len(self._stream_buffer) > 2000:
            display = "...[earlier]" + display[-1900:]
        result_area.update(display + f"\n\n{_('分析中')}{dots}")
        self.refresh()

    def finish_stream(self, result):
        """Complete the streaming display with the final structured result.

        Args:
            result: AnalysisResult object from the analyzer
        """
        self._streaming = False
        self._stream_buffer = ""

        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")

        # Build details text
        details_lines = [
            f"{_('综合评分:')}{result.sentiment_score}/100",
            f"{_('趋势预测:')}{result.trend_prediction}",
            f"{_('操作建议:')}{result.operation_advice}",
            f"{_('置信度:')}{result.confidence_level}",
            "",
        ]
        if result.trend_analysis:
            details_lines.append(f"{_('走势分析:')}{result.trend_analysis}")
        if result.analysis_summary:
            details_lines.append(f"\n{_('综合分析:')}{result.analysis_summary}")
        if result.risk_warning:
            details_lines.append(f"\n{_('风险提示:')}{result.risk_warning}")
        if result.key_points:
            details_lines.append(f"\n{_('核心看点:')}{result.key_points}")

        details = "\n".join(details_lines)

        # Determine verdict
        score = result.sentiment_score
        if score >= 70:
            verdict = _("看涨")
            verdict_color = "green"
        elif score >= 40:
            verdict = _("中性")
            verdict_color = "yellow"
        else:
            verdict = _("看跌")
            verdict_color = "red"

        # Extract catalysts and risks from dashboard if available
        catalysts = []
        risks = []
        if result.dashboard:
            catalysts = result.dashboard.get("intelligence", {}).get("positive_catalysts", [])
            risks = result.dashboard.get("intelligence", {}).get("risk_alerts", [])

        self.set_structured_result(verdict, verdict_color, score,
                                   catalysts, risks, details)

    def set_result(self, text: str):
        """Set plain text result (for errors)"""
        self._streaming = False
        self._stream_buffer = ""

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
        self._streaming = False
        self._stream_buffer = ""

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

    def finish_deep_analysis(self, result):
        """Display deep multi-agent analysis result with specialist breakdowns.

        Args:
            result: DeepAnalysisResult object or dict from the analyzer
        """
        self._streaming = False
        self._stream_buffer = ""

        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")

        # Handle both dict and object
        if isinstance(result, dict):
            score = result.get("composite_score", result.get("sentiment_score", 50))
            verdict = result.get("final_verdict", "中性")
            catalysts = result.get("key_catalysts", [])
            risks = result.get("risk_factors", [])
            tech = result.get("technical", {}) or {}
            fund = result.get("fundamental", {}) or {}
            news = result.get("news", {}) or {}
            trend = result.get("trend_prediction", "---")
            advice = result.get("operation_advice", "---")
            synthesis = result.get("synthesis_text", "")
        else:
            score = getattr(result, 'composite_score', 50)
            verdict = getattr(result, 'final_verdict', '中性')
            catalysts = getattr(result, 'key_catalysts', [])
            risks = getattr(result, 'risk_factors', [])
            tech = getattr(result, 'technical', {}) or {}
            fund = getattr(result, 'fundamental', {}) or {}
            news = getattr(result, 'news', {}) or {}
            trend = getattr(result, 'trend_prediction', '---')
            advice = getattr(result, 'operation_advice', '---')
            synthesis = getattr(result, 'synthesis_text', '')

        # Verdict
        if score >= 70:
            verdict_color = "green"
        elif score >= 40:
            verdict_color = "yellow"
        else:
            verdict_color = "red"

        # Build detail lines with specialist breakdowns
        lines = [
            f"{'='*30}",
            f"  {_('深度分析综合评分')}: {score}/100",
            f"  {_('最终研判')}: {verdict}",
            f"  {_('趋势预测')}: {trend}",
            f"  {_('操作建议')}: {advice}",
            f"",
            f"{'='*30}",
            f"  {_('技术面评分')}: {tech.get('score', 'N/A')}",
            f"  {_('基本面评分')}: {fund.get('score', 'N/A')}",
            f"  {_('消息面评分')}: {news.get('score', 'N/A')}",
        ]
        if tech.get('trend'):
            lines.append(f"  {_('技术趋势')}: {tech.get('trend')}")
        if tech.get('key_signals'):
            lines.append(f"  {_('技术信号')}: {', '.join(tech.get('key_signals', []))}")
        if fund.get('valuation'):
            lines.append(f"  {_('估值水平')}: {fund.get('valuation')}")
        if fund.get('key_metrics'):
            lines.append(f"  {_('核心指标')}: {', '.join(fund.get('key_metrics', []))}")
        if news.get('sentiment'):
            lines.append(f"  {_('舆情情绪')}: {news.get('sentiment')}")
        if synthesis:
            lines.append(f"\n{_('综合研判')}: {synthesis[:500]}")

        details = "\n".join(lines)

        self.set_structured_result(verdict, verdict_color, score,
                                   catalysts or [], risks or [], details)

    def finish_deep_error(self, message: str):
        """Display deep analysis error."""
        self._streaming = False
        self._stream_buffer = ""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_text = self.query_one("#progress-text", Static)
        progress_bar.visible = False
        progress_text.update("")
        self.query_one("#result-area", Static).update(f"{_('深度分析失败: ')}{message}")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
