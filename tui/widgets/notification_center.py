"""Notification Center panel -- accessible via 'N' key, shows notification history."""
from textual.widgets import Static
from textual.events import Key
from src.notification_center import Notification, get_notification_center

CATEGORIES = [
    ("all", "全部"),
    ("price_alert", "价格异动"),
    ("analysis_complete", "分析完成"),
    ("trade_executed", "交易执行"),
    ("system", "系统"),
    ("backtest_complete", "回测完成"),
]

CATEGORY_LABELS = dict(CATEGORIES)

LEVEL_ICONS = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}


class NotificationCenterPanel(Static):
    """Notification history panel with filtering."""

    def __init__(self, on_close=None):
        super().__init__()
        self._on_close = on_close
        self._nc = get_notification_center()
        self._filter_category = "all"
        self._notifications: list = []

    def compose(self):
        yield Static("", id="nc-title")
        yield Static("", id="nc-filters")
        yield Static("", id="nc-content")

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.min_height = 10
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 2)
        self.styles.border = ("heavy", "#4CAF50")
        self._render()

    def _render(self):
        # Title
        unread = self._nc.get_unread_count()
        badge = f" [{unread}]" if unread > 0 else ""
        title_label = f"{_('通知中心')}{badge}  [按键: 1-6筛选  M=全部已读  R=刷新  Esc=关闭]"
        title = self.query_one("#nc-title", Static)
        title.update(title_label)

        # Filters
        filter_lines = []
        for i, (cat_key, cat_label) in enumerate(CATEGORIES):
            marker = "▶" if cat_key == self._filter_category else " "
            filter_lines.append(f"[{marker}] {cat_label}")
        filters = self.query_one("#nc-filters", Static)
        filters.update("  ".join(filter_lines))

        # Content
        notifications = self._nc.get_all(limit=50, category=None if self._filter_category == "all" else self._filter_category)
        lines = []
        lines.append("  " + "─" * 60)
        if not notifications:
            lines.append(f"  {_('暂无通知')}")
        for n in notifications:
            icon = LEVEL_ICONS.get(n.level, "ℹ️")
            read_mark = " " if n.read else "●"
            ts = n.timestamp[:16] if n.timestamp else ""
            cat_label = CATEGORY_LABELS.get(n.category, n.category)
            lines.append(f"  {read_mark} {icon} [{cat_label}] {ts}")
            lines.append(f"     {n.title}")
            if n.message:
                lines.append(f"     {n.message[:80]}")
            lines.append("")
        content = self.query_one("#nc-content", Static)
        content.update("\n".join(lines))

    def on_key(self, event: Key):
        key = event.key.lower()
        if key == "escape":
            if self._on_close:
                self._on_close()
            return
        if key == "m":
            self._nc.mark_all_read()
            self._render()
            return
        if key == "r":
            self._render()
            return
        # Filter by number key
        try:
            idx = int(key) - 1
            if 0 <= idx < len(CATEGORIES):
                self._filter_category = CATEGORIES[idx][0]
                self._render()
        except (ValueError, IndexError):
            pass
