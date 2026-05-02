"""行情页面"""
import flet as ft
from datetime import datetime
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER


class MarketsPage(ft.UserControl):
    """行情展示页面"""

    def __init__(self, app, data_provider):
        super().__init__()
        self.app = app
        self._data_provider = data_provider

    def build(self):
        # 标题栏
        header = ft.Row([
            ft.Text("自选股行情", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.icons.REFRESH,
                on_click=self._refresh,
                tooltip="刷新",
            ),
        ])

        # 行情表格 - 初始显示加载占位
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("代码", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("名称", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("最新价", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("涨跌幅", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("成交量", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )

        self._table_container = ft.Container(
            content=ft.ListView([self.table], expand=True),
            padding=10,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        return ft.Container(
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
                ft.DataCell(ft.Text("点击刷新获取数据", color=TEXT_SECONDARY)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
            ])
        )
        self._table_container.update()

    def _load_data(self):
        """加载行情数据"""
        data = self._data_provider.get_data()
        for code, market_data in data.items():
            change_str = f"{market_data.change:+.2f}%" if market_data.change != 0 else "0.00%"
            change_color = SUCCESS_COLOR if market_data.change >= 0 else ERROR_COLOR
            self.table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(market_data.code)),
                    ft.DataCell(ft.Text(market_data.name)),
                    ft.DataCell(ft.Text(f"{market_data.price:.2f}")),
                    ft.DataCell(ft.Text(change_str, color=change_color)),
                    ft.DataCell(ft.Text(market_data.volume)),
                ])
            )

    async def _fetch_and_update(self):
        """异步获取数据并更新界面"""
        await self._data_provider.fetch_all()
        self.table.rows.clear()
        self._load_data()
        self.update()
        last_update = self._data_provider.get_last_update()
        self.app.update_status(last_update or datetime.now().strftime("%H:%M:%S"))

    def _refresh(self, e):
        """刷新数据"""
        self.app.page.run_task(self._fetch_and_update)