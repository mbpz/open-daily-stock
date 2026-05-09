"""Stock Screener Widget for TUI."""
from textual.widgets import Static, Button, Input, Select
from textual.containers import HorizontalScroll, Vertical
from tui.data.wrapper import DataProviderWrapper
from src.i18n import _


class ScreenerWidget(Static):
    """TUI stock screener widget with filter inputs and results table."""

    def __init__(self, data_provider: DataProviderWrapper = None, service_client=None):
        super().__init__()
        self._dp = data_provider
        self._service_client = service_client
        self._results = []

    def compose(self):
        yield Static(_("=== 股票选股器 ==="), id="screener-title")
        yield Static(_("筛选条件:"))
        # Market cap range
        yield Static(_("市值范围(亿):"))
        yield Input(placeholder="min", id="mc-min", classes="screener-input")
        yield Input(placeholder="max", id="mc-max", classes="screener-input")
        # PE range
        yield Static(_("市盈率(PE):"))
        yield Input(placeholder="min", id="pe-min", classes="screener-input")
        yield Input(placeholder="max", id="pe-max", classes="screener-input")
        # Change pct range
        yield Static(_("涨跌幅(%):"))
        yield Input(placeholder="min", id="pct-min", classes="screener-input")
        yield Input(placeholder="max", id="pct-max", classes="screener-input")
        # Industry
        yield Static(_("行业(可选):"))
        yield Input(placeholder=_("如: 银行"), id="industry", classes="screener-input")

        yield Button(_("开始筛选"), id="screener-btn", variant="primary")
        yield Static("", id="screener-status")
        # Results area
        yield Static(_("筛选结果:"), id="screener-results-label")
        yield Static("", id="screener-results", markup=True)

    def _render_data(self) -> str:
        """Render filtered results"""
        if not self._results:
            return _("  暂无结果，请设置筛选条件后点击 [开始筛选]")

        lines = [_("  代码        名称        价格      涨跌幅    市盈率    市值(亿)")]
        lines.append("  " + "-" * 70)
        for stock in self._results[:50]:  # Limit to 50 results
            code = stock.get("code", "")
            name = stock.get("name", "")
            price = stock.get("price", 0) or 0
            change_pct = stock.get("change_pct") or 0
            pe = stock.get("pe") or 0
            total_mv = stock.get("total_mv", 0) or 0

            emoji = "🟢" if change_pct > 0 else "🔴" if change_pct < 0 else "⚪"
            sign = "+" if change_pct > 0 else ""
            mv_b = total_mv / 1e8 if total_mv else 0

            lines.append(
                f"  {code:<10} {name:<8} {price:>8.2f} {emoji}{sign}{change_pct:>5.1f}% "
                f"{pe:>6.1f} {mv_b:>10.1f}"
            )
        return "\n".join(lines)

    def on_button_pressed(self, event):
        """Handle screener button press"""
        if event.button.id == "screener-btn":
            self._run_screener()

    def _run_screener(self):
        """Execute screener based on input values"""
        if self._service_client is None:
            self.query_one("#screener-status").update(_("服务未连接"))
            return

        # Get filter values
        mc_min = self._get_input_float("mc-min")
        mc_max = self._get_input_float("mc-max")
        pe_min = self._get_input_float("pe-min")
        pe_max = self._get_input_float("pe-max")
        pct_min = self._get_input_float("pct-min")
        pct_max = self._get_input_float("pct-max")
        industry = self.query_one("#industry").value.strip() or None

        # Build criteria
        criteria = {}
        if mc_min is not None:
            criteria["market_cap_min"] = mc_min
        if mc_max is not None:
            criteria["market_cap_max"] = mc_max
        if pe_min is not None:
            criteria["pe_min"] = pe_min
        if pe_max is not None:
            criteria["pe_max"] = pe_max
        if pct_min is not None:
            criteria["change_pct_min"] = pct_min
        if pct_max is not None:
            criteria["change_pct_max"] = pct_max
        if industry:
            criteria["industry"] = industry

        self.query_one("#screener-status").update(_("正在筛选..."))
        self.query_one("#screener-results").update("")

        # Run screener
        try:
            result = self._service_client.screen_stocks(criteria)
            if result.get("status") == "ok":
                self._results = result.get("data", [])
                count = result.get("count", len(self._results))
                self.query_one("#screener-status").update(
                    f"共找到 {count} 只股票"
                )
                self.query_one("#screener-results").update(self._render_data())
            else:
                self.query_one("#screener-status").update(
                    result.get("message", _("筛选失败"))
                )
        except Exception as e:
            self.query_one("#screener-status").update(f"{_('筛选失败: ')}{str(e)}")

    def _get_input_float(self, input_id: str) -> float | None:
        """Get float value from input field"""
        try:
            val = self.query_one(f"#{input_id}").value.strip()
            return float(val) if val else None
        except ValueError:
            return None

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)