"""Tasks module showing analysis job history."""
from textual.widgets import Static
from tui.data.task_store import TaskStore, TaskStatus

class TasksView(Static):
    def __init__(self, task_store: TaskStore):
        super().__init__()
        self._store = task_store

    def render(self) -> str:
        tasks = self._store.get_tasks()
        lines = ["  历史任务", "  " + "-" * 50]
        if not tasks:
            lines.append("  暂无任务记录")
            return "\n".join(lines)
        for t in tasks:
            status_icon = {"pending": "○", "running": "🔄", "done": "✅", "failed": "❌"}[t.status.value]
            lines.append(f"  {status_icon} {t.timestamp}  {t.code}")
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)