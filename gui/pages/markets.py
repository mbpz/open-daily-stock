"""行情页面"""
import flet as ft
from datetime import datetime
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER

class MarketsPage(ft.UserControl):
    """行情展示页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

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

        # 行情表格
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

        self._load_data()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                ft.Container(
                    content=ft.ListView([self.table], expand=True),
                    padding=10,
                    bgcolor=CARD_BG,
                    border_radius=10,
                ),
            ]),
            padding=10,
        )

    def _load_data(self):
        """加载行情数据"""
        example_data = [
            ("600519", "贵州茅台", "1690.00", "+0.60%", "1000万"),
            ("000001", "平安银行", "12.50", "+0.85%", "1500万"),
        ]
        for row in example_data:
            code, name, price, change, volume = row
            change_color = SUCCESS_COLOR if "+" in change else ERROR_COLOR
            self.table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(code)),
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(price)),
                    ft.DataCell(ft.Text(change, color=change_color)),
                    ft.DataCell(ft.Text(volume)),
                ])
            )

    def _refresh(self, e):
        """刷新数据"""
        self.table.rows.clear()
        self._load_data()
        self.update()
        self.app.update_status(datetime.now().strftime("%H:%M:%S"))
