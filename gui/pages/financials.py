"""财务报表页面"""
import flet as ft
from gui.components.async_task import AsyncTaskMixin
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR, ACCENT_COLOR, TEXT_SECONDARY
from src.i18n import _


class FinancialsPage(AsyncTaskMixin, ft.Container):
    """财务报表页面 - 显示利润表/资产负债表/现金流量表"""

    def __init__(self, app, service_client=None):
        # Init base container first, then the mixin (sets up cancellation token).
        ft.Container.__init__(self)
        AsyncTaskMixin.__init__(self, app)
        self.app = app
        self._client = service_client

        self._financial_data = None

        # Header
        header = ft.Text(_("财务报表"), size=24, weight=ft.FontWeight.BOLD)

        # Stock code input
        self._stock_input = ft.TextField(
            hint_text="如: 600519",
            width=200,
        )

        # Statement type dropdown
        self._type_dropdown = ft.Dropdown(
            width=200,
            options=[
                ft.dropdown.Option("income", _("利润表")),
                ft.dropdown.Option("balance", _("资产负债表")),
                ft.dropdown.Option("cashflow", _("现金流量表")),
            ],
            value="income",
            label=_("报表类型"),
        )

        # Query button
        self._query_btn = ft.Button(
            _("查询"),
            icon=ft.Icons.SEARCH,
            on_click=self._query_financials,
            bgcolor=ACCENT_COLOR,
            color=ft.Colors.WHITE,
        )

        input_row = ft.Row([
            ft.Text(_("股票代码:"), width=80),
            self._stock_input,
            ft.Container(width=10),
            self._type_dropdown,
            ft.Container(width=10),
            self._query_btn,
        ])

        # Status text
        self._status_text = ft.Text("", color=TEXT_SECONDARY)

        # Data table
        self._data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(_("项目"), weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )

        self._table_container = ft.Container(
            content=ft.ListView([self._data_table], expand=True),
            padding=10,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        # Result area (shown until first query)
        self._result_area = ft.Container(
            content=ft.Text(_("输入股票代码查询财务报表"), color=TEXT_SECONDARY),
            padding=20,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=True,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                input_row,
                ft.Container(height=5),
                self._status_text,
                ft.Container(height=10),
                self._result_area,
                self._table_container,
            ], scroll=ft.ScrollMode.AUTO),
            padding=10,
        )

    def _query_financials(self, e):
        """查询财务报表 — uses AsyncTaskMixin for cancellation + UI helpers."""
        code = self._stock_input.value.strip()
        if not code:
            self.set_status(f"⚠️ {_('请输入股票代码')}")
            return

        statement_type = self._type_dropdown.value
        self.set_status(_("正在查询..."))
        self.run_async(self._fetch_financials, code, statement_type)

    async def _fetch_financials(self, code: str, statement_type: str):
        """异步获取财务数据 — co-operative cancellation via mixin."""
        import asyncio

        try:
            if self.check_cancelled():
                return
            if self._client:
                result = await asyncio.to_thread(
                    self._client._send_request,
                    "get_financials",
                    {"code": code, "type": statement_type},
                )
            else:
                from src.data_service import DataService
                service = DataService()
                result = await asyncio.to_thread(
                    service._handle_request,
                    {"action": "get_financials", "code": code, "type": statement_type},
                )

            if self.check_cancelled():
                return

            if result.get("status") == "ok":
                self._financial_data = result.get("data", {})
                self._display_table()
                self.set_status("")
            else:
                self.set_status(result.get("message", _("查询失败")))
                self._result_area.content = ft.Text(
                    result.get("message", _("查询失败")),
                    color=ERROR_COLOR,
                )
                self._result_area.visible = True
                self._result_area.update()

        except Exception as ex:
            self.set_status(f"{_('查询失败: ')}{str(ex)}")

    def _display_table(self):
        """显示财务数据表格"""
        data = self._financial_data
        if not data or not data.get("items"):
            self._result_area.content = ft.Text(_("无财务数据"), color=TEXT_SECONDARY)
            self._result_area.visible = True
            self._result_area.update()
            return

        self._result_area.visible = False
        self._result_area.update()

        periods = data.get("periods", [])
        items = data.get("items", [])

        # Build columns: project name + period columns
        columns = [ft.DataColumn(ft.Text(_("项目"), weight=ft.FontWeight.BOLD))]
        for p in periods:
            # Show only year+quarter portion
            display_period = p[:7] if len(p) > 7 else p
            columns.append(ft.DataColumn(ft.Text(display_period, size=11, weight=ft.FontWeight.BOLD)))

        self._data_table.columns = columns

        # Build rows
        self._data_table.rows.clear()
        for item in items:
            cells = [ft.DataCell(ft.Text(item["name"], size=12))]
            for val in item.get("values", []):
                if val is None:
                    cells.append(ft.DataCell(ft.Text("-", size=11)))
                elif val > 0:
                    cells.append(ft.DataCell(ft.Text(self._format_value(val), size=11, color=SUCCESS_COLOR)))
                elif val < 0:
                    cells.append(ft.DataCell(ft.Text(self._format_value(val), size=11, color=ERROR_COLOR)))
                else:
                    cells.append(ft.DataCell(ft.Text("0", size=11)))
            self._data_table.rows.append(ft.DataRow(cells=cells))

        self._table_container.update()
        self.update()

    @staticmethod
    def _format_value(value):
        """Format financial values in billions/millions"""
        if abs(value) >= 1e8:
            return f"{value / 1e8:.2f}亿"
        elif abs(value) >= 1e4:
            return f"{value / 1e4:.2f}万"
        else:
            return f"{value:.2f}"
