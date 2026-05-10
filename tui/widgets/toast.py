"""Toast notification overlay for TUI -- bottom-right corner, auto-dismiss."""
from textual.widgets import Static
from textual.timer import Timer
from src.notification_center import Notification
from src.i18n import _


LEVEL_ICONS = {
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
    "success": "✅",
}

LEVEL_COLORS = {
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
}


class Toast(Static):
    """A single self-dismissing toast notification."""

    def __init__(self, notification: Notification, dismiss_seconds: float = 5.0):
        self._notification = notification
        self._dismiss_seconds = dismiss_seconds
        self._timer: Timer | None = None
        super().__init__()

    def on_mount(self):
        self.styles.width = "auto"
        self.styles.max_width = 50
        self.styles.height = "auto"
        self.styles.dock = "bottom"
        self.styles.margin = (0, 1, 1, 0)
        self._render()
        # Auto-dismiss timer
        self._timer = self.set_timer(self._dismiss_seconds, self._dismiss)

    def _render(self):
        icon = LEVEL_ICONS.get(self._notification.level, "ℹ️")
        color = LEVEL_COLORS.get(self._notification.level, "white")
        title = self._notification.title[:30]
        msg = self._notification.message[:60]
        text = f" [{color}]{icon} {title}[/]"
        if msg:
            text += f"\n   {msg}"
        self.update(text)

    def _dismiss(self):
        try:
            self.remove()
        except Exception:
            pass

    def on_click(self):
        """Click to dismiss early."""
        try:
            self._notification.read = True
        except Exception:
            pass
        self._dismiss()


class ToastContainer(Static):
    """A container that stacks toast notifications vertically in the bottom-right corner."""

    def __init__(self):
        super().__init__()
        self._max_visible = 3

    def on_mount(self):
        self.styles.dock = "right"
        self.styles.width = "auto"
        self.styles.height = "auto"
        self.styles.layer = "overlay"
        self.styles.margin = (0, 1, 1, 0)

    def show_toast(self, notification: Notification, dismiss_seconds: float = 5.0):
        """Add a new toast. Removes oldest if over max_visible."""
        toasts = self.query(Toast)
        while len(toasts) >= self._max_visible:
            first = toasts.first()
            if isinstance(first, Toast):
                try:
                    first.remove()
                except Exception:
                    pass
            toasts = self.query(Toast)
        self.mount(Toast(notification, dismiss_seconds))


def get_toast_container() -> ToastContainer:
    """Get or create a shared ToastContainer instance."""
    return ToastContainer()
