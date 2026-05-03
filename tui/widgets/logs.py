"""Logs module showing log output from existing log files."""
from pathlib import Path
from textual.widgets import Static, Input
from textual.events import Key
from datetime import datetime


class LogsView(Static):
    """Display log entries with filtering."""
    def __init__(self):
        super().__init__()
        self._filter_level = "all"  # all/info/warning/error
        self._search_query = ""
        self._entries: list = []
        self._log_dir = Path("logs")
        self._result_count = 0
        self._search_input: Input | None = None

    def load_logs(self):
        """Load recent log entries from logs/ directory."""
        self._entries = []
        if not self._log_dir.exists():
            return
        # Read today's log file if it exists
        today = datetime.now().strftime("%Y%m%d")
        log_file = self._log_dir / f"stock_analysis_{today}.log"
        if log_file.exists():
            self._load_file(log_file)
        # Also check debug log
        debug_file = self._log_dir / f"stock_analysis_debug_{today}.log"
        if debug_file.exists():
            self._load_file(debug_file)

    def _load_file(self, path: Path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f.readlines()[-500:]:  # last 500 lines
                    self._entries.append(line.rstrip())
        except Exception:
            pass

    def set_filter(self, level: str):
        self._filter_level = level
        self.refresh()

    def set_search(self, query: str):
        """Set search query and refresh"""
        self._search_query = query.lower()
        self.refresh()

    def render(self) -> str:
        self.load_logs()
        lines = [f"  日志 (过滤: {self._filter_level})", f"  搜索: {self._search_query} | 结果: {self._result_count}", "  " + "-" * 60]
        if not self._entries:
            lines.append("  暂无日志")
            return "\n".join(lines)
        self._result_count = 0
        for line in self._entries[-100:]:  # last 100 lines
            if self._filter_level != "all" and self._filter_level not in line.lower():
                continue
            if self._search_query and self._search_query not in line.lower():
                continue
            self._result_count += 1
            lines.append(f"  {line}")
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
        self.load_logs()