"""Tasks module showing analysis job history."""
import json
from textual.widgets import Static
from textual.app import ComposeResult
from textual.binding import Binding
from tui.data.task_store import TaskStore, TaskStatus
from src.storage import get_db

class TasksView(Static):
    """Tasks widget showing historical analysis tasks."""

    BINDINGS = [
        Binding("enter", "show_detail", "查看详情", show=True),
        Binding("r", "refresh", "刷新", show=True),
    ]

    def __init__(self, task_store: TaskStore):
        super().__init__()
        self._store = task_store
        self._db = get_db()
        self._selected_index = 0
        self._tasks_data = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(self._render_tasks(), id="tasks-content")

    def _render_tasks(self) -> str:
        """Render the tasks list."""
        lines = ["  历史任务 (按 Enter 查看详情)", "  " + "-" * 60]

        # Load from database
        try:
            self._tasks_data = self._db.get_analysis_history(limit=50)
        except Exception:
            self._tasks_data = []

        if not self._tasks_data:
            # Fallback to task_store
            tasks = self._store.get_tasks()
            if not tasks:
                lines.append("  暂无任务记录")
                return "\n".join(lines)
            for i, t in enumerate(tasks):
                marker = " >" if i == self._selected_index else "  "
                status_icon = {"pending": "○", "running": "🔄", "done": "✅", "failed": "❌"}[t.status.value]
                lines.append(f"{marker}{status_icon} {t.timestamp}  {t.code}")
        else:
            for i, task in enumerate(self._tasks_data):
                marker = " >" if i == self._selected_index else "  "
                status_str = task.status.upper() if task.status else "UNKNOWN"
                status_icon = {"PENDING": "⏳", "RUNNING": "🔄", "DONE": "✅", "FAILED": "❌"}.get(status_str, "❓")
                timestamp_str = task.timestamp.strftime("%Y-%m-%d %H:%M") if task.timestamp else "N/A"
                lines.append(f"{marker}{status_icon} {timestamp_str}  {task.code}")

                # Show brief result
                if task.result_json:
                    try:
                        result_data = json.loads(task.result_json)
                        advice = result_data.get('operation_advice', 'N/A')
                        score = result_data.get('sentiment_score', 'N/A')
                        lines.append(f"     结果: {advice} (评分: {score})")
                    except:
                        pass

        lines.append("")
        lines.append("  操作: ↑↓ 选择, Enter 查看详情, R 刷新")
        return "\n".join(lines)

    def watch_tasks(self) -> None:
        """Watch for task updates."""
        self._refresh()

    def _refresh(self) -> None:
        """Refresh the tasks list."""
        self._selected_index = 0
        content = self.query_one("#tasks-content", Static)
        content.update(self._render_tasks())

    def action_refresh(self) -> None:
        """Refresh the tasks list."""
        self._refresh()

    def action_show_detail(self) -> None:
        """Show detail for selected task."""
        if not self._tasks_data or self._selected_index >= len(self._tasks_data):
            return

        task = self._tasks_data[self._selected_index]
        if not task.result_json:
            return

        try:
            result_data = json.loads(task.result_json)
        except:
            return

        # Build detail text
        detail_lines = [
            "",
            "=" * 60,
            f"  分析详情 - {task.code}",
            "=" * 60,
            f"  时间: {task.timestamp.strftime('%Y-%m-%d %H:%M') if task.timestamp else 'N/A'}",
            f"  状态: {task.status}",
            "-" * 60,
            f"  综合评分: {result_data.get('sentiment_score', 'N/A')}",
            f"  趋势预测: {result_data.get('trend_prediction', 'N/A')}",
            f"  操作建议: {result_data.get('operation_advice', 'N/A')}",
            f"  置信度: {result_data.get('confidence_level', 'N/A')}",
            "-" * 60,
            f"  走势分析:",
            f"  {result_data.get('trend_analysis', 'N/A') or '无'}",
            "-" * 60,
            f"  短期展望:",
            f"  {result_data.get('short_term_outlook', 'N/A') or '无'}",
            "-" * 60,
            f"  支撑位/压力位:",
            f"  {result_data.get('support_resistance', 'N/A') or '无'}",
            "-" * 60,
            f"  风险提示:",
            f"  {result_data.get('risk_alert', 'N/A') or '无'}",
            "=" * 60,
            "",
            "  按 Esc 关闭",
        ]

        detail_text = "\n".join(detail_lines)

        # Show in a modal panel
        from textual.widgets import Static
        from textual.containers import Container

        self._detail_panel = Container(
            Static(detail_text, id="detail-text"),
            id="detail-panel",
        )

        # This would need proper implementation in Textual
        # For now, just print to log
        self.app.log(detail_text)

    def on_key(self, event) -> None:
        """Handle key events for navigation."""
        if event.key == "up":
            if self._selected_index > 0:
                self._selected_index -= 1
                self._refresh()
        elif event.key == "down":
            max_idx = len(self._tasks_data) - 1 if self._tasks_data else len(self._store.get_tasks()) - 1
            if self._selected_index < max_idx:
                self._selected_index += 1
                self._refresh()

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)