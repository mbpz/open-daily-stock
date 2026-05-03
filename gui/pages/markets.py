"""行情页面"""
import flet as ft
import asyncio
from datetime import datetime
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER
from src.i18n import _


class MarketsPage(ft.Container):
    """行情展示页面"""

    def __init__(self, app, service_client):
        super().__init__()
        self.app = app
        self._client = service_client

        # 标题栏
        header = ft.Row([
            ft.Text(_("自选股行情"), size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                on_click=self._refresh,
                tooltip=_("刷新"),
            ),
        ])

        # 行情表格 - 初始显示加载占位
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(_("代码"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("名称"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("最新价"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("涨跌幅"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("成交量"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("操作"), weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )

        self._table_container = ft.Container(
            content=ft.ListView([self.table], expand=True),
            padding=10,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                self._table_container,
            ]),
            padding=10,
        )

    def on_mount(self):
        """生命周期钩子 - 页面挂载时触发异步数据获取"""
        self.app.page.run_task(self._fetch_and_update)

    def _show_placeholder(self):
        """显示加载占位符"""
        self.table.rows.clear()
        self.table.rows.append(
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(_("点击刷新获取数据"), color=TEXT_SECONDARY)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
            ])
        )
        self._table_container.update()

    def _load_data(self, markets):
        """加载行情数据"""
        for market in markets:
            change = market.get('change', 0)
            change_str = f"{change:+.2f}%" if change != 0 else "0.00%"
            change_color = SUCCESS_COLOR if change >= 0 else ERROR_COLOR
            code = market.get('code', '')
            self.table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(code)),
                    ft.DataCell(ft.Text(market.get('name', ''))),
                    ft.DataCell(ft.Text(f"{market.get('price', 0):.2f}")),
                    ft.DataCell(ft.Text(change_str, color=change_color)),
                    ft.DataCell(ft.Text(market.get('volume', ''))),
                    ft.DataCell(
                        ft.IconButton(
                            icon=ft.Icons.SHOW_CHART,
                            tooltip=_("查看K线"),
                            on_click=lambda e, c=code: self._show_chart(c),
                        )
                    ),
                ])
            )

    def _show_chart(self, code):
        """打开K线图表页面"""
        self.app.nav_index = 0  # 切换到K线页面
        self.app.nav_rail.selected_index = 0
        self.app.page.run_task(self.app._load_page, "chart")
        # 设置股票代码到chart页面的输入框
        self.app.page.run_task(self._set_chart_code, code)

    async def _set_chart_code(self, code):
        """设置chart页面的股票代码"""
        await asyncio.sleep(0.1)  # 等待页面加载
        if hasattr(self.app, 'content_area') and hasattr(self.app.content_area, 'content'):
            content = self.app.content_area.content
            if hasattr(content, '_code_input'):
                content._code_input.value = code
                content._code_input.update()
                content._show_chart(None)  # 自动触发显示

    async def _fetch_and_update(self):
        """异步获取数据并更新界面"""
        markets = self._client.get_markets()
        self.table.rows.clear()
        self._load_data(markets)
        self.update()
        self.app.update_status(datetime.now().strftime("%H:%M:%S"))

    def _refresh(self, e):
        """刷新数据"""
        self.app.page.run_task(self._fetch_and_update)