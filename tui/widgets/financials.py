"""Financial Statement Widget for TUI."""
from textual.widgets import Static, Button, Input, Select
from src.i18n import _


class FinancialsWidget(Static):
    """TUI financial statement widget with type selector and results table."""

    def __init__(self, service_client=None):
        super().__init__()
        self._service_client = service_client
        self._financial_data = None
        self._statement_type = "income"

    def compose(self):
        yield Static(_("=== 财务报表 ==="), id="fin-title")

        # Stock code input
        yield Static(_("股票代码:"))
        yield Input(placeholder="600519", id="fin-code", classes="fin-input")

        # Statement type selection
        yield Static(_("报表类型:"))
        yield Select(
            [
                ("income", _("利润表")),
                ("balance", _("资产负债表")),
                ("cashflow", _("现金流量表")),
            ],
            value="income",
            id="fin-type",
        )

        yield Button(_("查询"), id="fin-query-btn", variant="primary")
        yield Static("", id="fin-status")

        # Results area
        yield Static(_("查询结果:"), id="fin-results-label")
        yield Static("", id="fin-results")

    def on_button_pressed(self, event):
        """Handle query button press"""
        if event.button.id == "fin-query-btn":
            self._run_query()

    def on_select_changed(self, event):
        """Handle statement type change"""
        if event.select.id == "fin-type":
            self._statement_type = event.value

    def _run_query(self):
        """Execute financial statement query"""
        code_input = self.query_one("#fin-code")
        code = code_input.value.strip()

        if not code:
            self.query_one("#fin-status").update(_("请输入股票代码"))
            return

        self.query_one("#fin-status").update(_("正在查询..."))

        try:
            if self._service_client:
                result = self._service_client._send_request(
                    "get_financials",
                    {"code": code, "type": self._statement_type},
                )
            else:
                from src.data_service import DataService
                service = DataService()
                result = service._handle_request({
                    "action": "get_financials",
                    "code": code,
                    "type": self._statement_type,
                })

            if result.get("status") == "ok":
                self._financial_data = result.get("data", {})
                self.query_one("#fin-status").update("")
                self.query_one("#fin-results").update(self._render_table())
            else:
                self.query_one("#fin-status").update(
                    result.get("message", _("查询失败"))
                )
                self.query_one("#fin-results").update("")

        except Exception as e:
            self.query_one("#fin-status").update(f"{_('查询失败: ')}{str(e)}")
            self.query_one("#fin-results").update("")

    def _render_table(self) -> str:
        """Render financial data as a table"""
        data = self._financial_data
        if not data or not data.get("items"):
            return _("  无财务数据")

        periods = data.get("periods", [])
        items = data.get("items", [])

        # Build header
        header_parts = ["项目"]
        for p in periods:
            display = p[:7] if len(p) > 7 else p
            header_parts.append(f"{display:>12}")
        header = "  " + "  ".join(header_parts)

        lines = [header]
        lines.append("  " + "-" * (len(header_parts) * 14))

        # Build rows
        for item in items:
            name = item["name"][:10]  # Truncate name
            row_parts = [f"{name:<10}"]
            for val in item.get("values", []):
                if val is None:
                    row_parts.append(f"{'-':>12}")
                else:
                    row_parts.append(f"{self._format_value(val):>12}")
            lines.append("  " + "  ".join(row_parts))

        # Add legend
        lines.append("")
        lines.append(_("  单位: 亿元"))
        lines.append(_("  正值=收入/流入，负值=支出/流出"))

        return "\n".join(lines)

    @staticmethod
    def _format_value(value):
        """Format financial values in appropriate units"""
        if abs(value) >= 1e8:
            return f"{value / 1e8:.2f}亿"
        elif abs(value) >= 1e4:
            return f"{value / 1e4:.2f}万"
        else:
            return f"{value:.2f}"

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
