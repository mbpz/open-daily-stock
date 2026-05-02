"""任务历史页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, SUCCESS_COLOR

class TasksPage(ft.UserControl):
    """任务历史页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        header = ft.Text("历史任务", size=24, weight=ft.FontWeight.BOLD)

        self.task_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
        )

        self._load_tasks()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                self.task_list,
            ]),
            padding=10,
        )

    def _load_tasks(self):
        """加载任务历史"""
        # TODO: 接入 TaskStore
        example_tasks = [
            ("600519", "2026-05-01 10:30", "完成", "75分"),
            ("000001", "2026-05-01 09:15", "完成", "68分"),
        ]
        for code, time_str, status, score in example_tasks:
            self.task_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{code}", weight=ft.FontWeight.BOLD),
                            ft.Text(time_str, color=TEXT_SECONDARY, size=12),
                        ]),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Text(status, color=SUCCESS_COLOR),
                            padding=5,
                            bgcolor="#1b5e20",
                            border_radius=5,
                        ),
                        ft.Text(f"评分: {score}"),
                    ]),
                    padding=15,
                    bgcolor=CARD_BG,
                    border_radius=10,
                )
            )