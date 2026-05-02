"""分析页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR, ACCENT_COLOR

class AnalyzePage(ft.UserControl):
    """股票分析页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        header = ft.Text("股票分析", size=24, weight=ft.FontWeight.BOLD)

        input_row = ft.Row([
            ft.Text("股票代码:", width=100),
            self._stock_input := ft.TextField(
                hint_text="如: 600519",
                width=200,
            ),
            ft.Container(width=20),
            ft.ElevatedButton(
                "开始分析",
                icon=ft.icons.PLAY_ARROW,
                on_click=self._start_analysis,
                bgcolor=ACCENT_COLOR,
                color=ft.WHITE,
            ),
        ])

        self._result_area = ft.Container(
            content=ft.Text("分析结果将显示在这里", color="#a0a0a0"),
            padding=20,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=True,
        )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                input_row,
                ft.Container(height=20),
                self._result_area,
            ]),
            padding=10,
        )

    def _start_analysis(self, e):
        """开始分析"""
        code = self._stock_input.value.strip()
        if not code:
            self._show_result("请输入股票代码", is_error=True)
            return

        self._result_area.content = ft.Column([
            ft.ProgressRing(width=50, height=50),
            ft.Text(f"正在分析 {code}..."),
        ])
        self._result_area.update()

        # TODO: 接入 Pipeline
        import time
        time.sleep(1)

        result = f"分析完成: {code}\n买入建议: 持有\n评分: 75分"
        self._show_result(result)

    def _show_result(self, message: str, is_error: bool = False):
        """显示结果"""
        color = ERROR_COLOR if is_error else SUCCESS_COLOR
        self._result_area.content = ft.Text(message, color=color)
        self._result_area.update()