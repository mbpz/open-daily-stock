"""任务历史页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, DONE_BG

# Status icons
STATUS_ICONS = {
    "PENDING": "⏳",
    "RUNNING": "🔄",
    "DONE": "✅",
    "FAILED": "❌",
}

# Status colors
STATUS_COLORS = {
    "PENDING": WARNING_COLOR,
    "RUNNING": TEXT_SECONDARY,
    "DONE": SUCCESS_COLOR,
    "FAILED": ERROR_COLOR,
}

class TasksPage(ft.UserControl):
    """任务历史页面"""

    def __init__(self, app, task_store=None):
        super().__init__()
        self.app = app
        self.task_store = task_store

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
        # Clear existing controls
        self.task_list.controls.clear()

        if self.task_store is None:
            return

        tasks = self.task_store.get_tasks()
        for task in tasks:
            status_str = task.status.name
            status_icon = STATUS_ICONS.get(status_str, "❓")
            status_color = STATUS_COLORS.get(status_str, TEXT_SECONDARY)

            # Build result text if available
            result_text = ""
            if task.result:
                result_text = task.result
            elif task.error:
                result_text = f"Error: {task.error}"

            card_content = ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text(f"{task.code}", weight=ft.FontWeight.BOLD),
                        ft.Text(task.timestamp, color=TEXT_SECONDARY, size=12),
                    ]),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(f"{status_icon} {status_str}", color=status_color),
                        padding=5,
                        bgcolor=DONE_BG if status_str == "DONE" else "#2d2d2d",
                        border_radius=5,
                    ),
                ]),
            ])

            # Add result info if available
            if result_text:
                card_content.controls.append(
                    ft.Text(f"Result: {result_text[:50]}..." if len(result_text) > 50 else f"Result: {result_text}", size=12)
                )

            self.task_list.controls.append(
                ft.Container(
                    content=card_content,
                    padding=15,
                    bgcolor=CARD_BG,
                    border_radius=10,
                )
            )