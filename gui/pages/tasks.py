"""任务历史页面"""
import flet as ft
import json
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, DONE_BG
from src.storage import get_db

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

class TasksPage(ft.Container):
    """任务历史页面"""

    def __init__(self, app, task_store=None):
        super().__init__()
        self.app = app
        self.task_store = task_store
        self._db = get_db()

        header = ft.Text("历史任务", size=24, weight=ft.FontWeight.BOLD)

        self.task_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
        )

        self._load_tasks()

        self.content = ft.Container(
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

        # Load from database
        try:
            history_records = self._db.get_analysis_history(limit=100)
        except Exception as e:
            # Fallback to task_store if database fails
            history_records = []

        if history_records:
            for record in history_records:
                status_str = record.status.upper()
                status_icon = STATUS_ICONS.get(status_str, "❓")
                status_color = STATUS_COLORS.get(status_str, TEXT_SECONDARY)

                # Parse result JSON if available
                result_text = ""
                if record.result_json:
                    try:
                        result_data = json.loads(record.result_json)
                        result_text = f"{result_data.get('operation_advice', 'N/A')} | 评分: {result_data.get('sentiment_score', 'N/A')}"
                    except:
                        result_text = record.result_json[:50] if len(record.result_json) > 50 else record.result_json

                # Format timestamp
                timestamp_str = record.timestamp.strftime("%Y-%m-%d %H:%M") if record.timestamp else "N/A"

                card_content = ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(f"{record.code}", weight=ft.FontWeight.BOLD),
                            ft.Text(timestamp_str, color=TEXT_SECONDARY, size=12),
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
                        ft.Text(f"Result: {result_text}", size=12)
                    )

                # Make card clickable to show detail
                card = ft.Container(
                    content=card_content,
                    padding=15,
                    bgcolor=CARD_BG,
                    border_radius=10,
                    on_click=lambda e, r=record: self._show_result_detail(r),
                )
                self.task_list.controls.append(card)
        else:
            # Fallback to task_store if no database records
            if self.task_store:
                for task in self.task_store.get_tasks():
                    status_str = task.status.name
                    status_icon = STATUS_ICONS.get(status_str, "❓")
                    status_color = STATUS_COLORS.get(status_str, TEXT_SECONDARY)

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

    def _show_result_detail(self, record):
        """Show full analysis result in a dialog"""
        if not record.result_json:
            return

        try:
            result_data = json.loads(record.result_json)
        except:
            return

        # Build detail content
        detail_content = ft.Column([
            ft.Text(f"股票代码: {record.code}", weight=ft.FontWeight.BOLD, size=18),
            ft.Text(f"时间: {record.timestamp.strftime('%Y-%m-%d %H:%M') if record.timestamp else 'N/A'}", size=14),
            ft.Divider(),
            ft.Text(f"综合评分: {result_data.get('sentiment_score', 'N/A')}", size=16),
            ft.Text(f"趋势预测: {result_data.get('trend_prediction', 'N/A')}", size=16),
            ft.Text(f"操作建议: {result_data.get('operation_advice', 'N/A')}", size=16),
            ft.Text(f"置信度: {result_data.get('confidence_level', 'N/A')}", size=16),
            ft.Divider(),
            ft.Text("走势分析:", weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('trend_analysis', 'N/A') or '无'),
            ft.Divider(),
            ft.Text("短期展望:", weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('short_term_outlook', 'N/A') or '无'),
            ft.Divider(),
            ft.Text("支撑位/压力位:", weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('support_resistance', 'N/A') or '无'),
            ft.Divider(),
            ft.Text("风险提示:", weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('risk_alert', 'N/A') or '无'),
        ], scroll=ft.ScrollMode.AUTO)

        dialog = ft.AlertDialog(
            title=ft.Text(f"分析详情 - {record.code}"),
            content=detail_content,
            actions=[
                ft.TextButton("关闭", on_click=lambda e: self._close_dialog())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._dialog = dialog
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _close_dialog(self):
        """Close the detail dialog"""
        if hasattr(self, '_dialog') and self._dialog:
            self._dialog.open = False
            self.page.update()

    def refresh(self):
        """Refresh the task list"""
        self._load_tasks()
        if hasattr(self, 'content'):
            self.content.update()