"""任务历史页面"""
import flet as ft
import logging
logger = logging.getLogger(__name__)
import json
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, DONE_BG
from src.i18n import _
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

        header = ft.Text(_("历史任务"), size=24, weight=ft.FontWeight.BOLD)

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

    def _normalize(self, record):
        """Convert DB or TaskStore record to normalized dict."""
        if hasattr(record, 'to_dict'):
            d = record.to_dict()
            return {
                'code': d.get('code', ''),
                'status': str(d.get('status', '')).upper(),
                'timestamp': d.get('timestamp', 'N/A') or 'N/A',
                'result': d.get('result_json') or d.get('result'),
                '_record': record,
            }
        code = getattr(record, 'code', '')
        status_val = getattr(record, 'status', '')
        if hasattr(status_val, 'upper'):
            status_str = str(status_val).upper()
        elif hasattr(status_val, 'name'):
            status_str = str(status_val.name).upper()
        else:
            status_str = str(status_val).upper()
        timestamp_val = getattr(record, 'timestamp', None)
        if hasattr(timestamp_val, 'strftime'):
            timestamp_str = timestamp_val.strftime("%Y-%m-%d %H:%M")
        elif isinstance(timestamp_val, str):
            timestamp_str = timestamp_val
        else:
            timestamp_str = "N/A"
        result_val = getattr(record, 'result_json', None) or getattr(record, 'result', None)
        return {
            'code': code,
            'status': status_str,
            'timestamp': timestamp_str,
            'result': result_val,
            '_record': record,
        }

    def _load_tasks(self):
        """加载任务历史"""
        self.task_list.controls.clear()

        if self.task_store is not None:
            history_records = self.task_store.get_tasks()
        else:
            try:
                history_records = self._db.get_analysis_history(limit=100)
            except Exception as e:
                history_records = []

        if history_records:
            for record in history_records:
                r = self._normalize(record)
                status_str = r['status']
                status_icon = STATUS_ICONS.get(status_str, "❓")
                status_color = STATUS_COLORS.get(status_str, TEXT_SECONDARY)

                result_text = ""
                if r['result']:
                    try:
                        result_data = json.loads(r['result'])
                        result_text = f"{result_data.get('operation_advice', 'N/A')} | 评分: {result_data.get('sentiment_score', 'N/A')}"
                    except Exception:
                        result_text = str(r['result'])[:50]

                card_content = ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Text(f"{r['code']}", weight=ft.FontWeight.BOLD),
                            ft.Text(r['timestamp'], color=TEXT_SECONDARY, size=12),
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
                        ft.Text(f"Result: {result_text}", size=12)
                    )

                card = ft.Container(
                    content=card_content,
                    padding=15,
                    bgcolor=CARD_BG,
                    border_radius=10,
                    on_click=lambda e, r=r['_record']: self._show_result_detail(r),
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
        except (ValueError, TypeError) as e:
            logger.warning(f"解析任务结果 JSON 失败 (task_id={record.task_id}): {e}")
            return

        # Build detail content
        detail_content = ft.Column([
            ft.Text(f"{_('股票代码: ')}{record.code}", weight=ft.FontWeight.BOLD, size=18),
            ft.Text(f"{_('时间: ')}{record.timestamp.strftime('%Y-%m-%d %H:%M') if record.timestamp else 'N/A'}", size=14),
            ft.Divider(),
            ft.Text(f"{_('综合评分:')}{result_data.get('sentiment_score', 'N/A')}", size=16),
            ft.Text(f"{_('趋势预测:')}{result_data.get('trend_prediction', 'N/A')}", size=16),
            ft.Text(f"{_('操作建议:')}{result_data.get('operation_advice', 'N/A')}", size=16),
            ft.Text(f"{_('置信度:')}{result_data.get('confidence_level', 'N/A')}", size=16),
            ft.Divider(),
            ft.Text(_("走势分析:"), weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('trend_analysis', 'N/A') or 'N/A'),
            ft.Divider(),
            ft.Text(_("短期展望:"), weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('short_term_outlook', 'N/A') or 'N/A'),
            ft.Divider(),
            ft.Text(_("支撑位/压力位:"), weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('support_resistance', 'N/A') or 'N/A'),
            ft.Divider(),
            ft.Text(_("风险提示:"), weight=ft.FontWeight.BOLD),
            ft.Text(result_data.get('risk_alert', 'N/A') or 'N/A'),
        ], scroll=ft.ScrollMode.AUTO)

        dialog = ft.AlertDialog(
            title=ft.Text(f"{_('分析详情 - ')}{record.code}"),
            content=detail_content,
            actions=[
                ft.TextButton(_("关闭"), on_click=lambda e: self._close_dialog())
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