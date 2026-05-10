"""通知中心页面 - GUI notification history panel."""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, TEXT_PRIMARY
from src.notification_center import get_notification_center, Notification
from src.i18n import _

CATEGORIES = [
    ("all", "全部"),
    ("price_alert", "价格异动"),
    ("analysis_complete", "分析完成"),
    ("trade_executed", "交易执行"),
    ("system", "系统"),
    ("backtest_complete", "回测完成"),
]

CATEGORY_LABELS = dict(CATEGORIES)

LEVEL_COLORS = {
    "info": ft.Colors.BLUE,
    "warning": ft.Colors.ORANGE,
    "error": ft.Colors.RED,
    "success": ft.Colors.GREEN,
}

LEVEL_ICONS = {
    "info": ft.Icons.INFO,
    "warning": ft.Icons.WARNING,
    "error": ft.Icons.ERROR,
    "success": ft.Icons.CHECK_CIRCLE,
}


class NotificationsPage(ft.Container):
    """Notification history page with filtering."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._nc = get_notification_center()
        self._filter_category = "all"

        # Header
        header = ft.Text(_("通知中心"), size=24, weight=ft.FontWeight.BOLD)

        # Filter chips
        self._filter_chips = ft.Row(
            controls=[
                ft.FilterChip(
                    label=ft.Text(label),
                    selected=(key == "all"),
                    on_select=lambda e, k=key: self._on_filter(k, e),
                )
                for key, label in CATEGORIES
            ],
            scroll=ft.ScrollMode.AUTO,
        )

        # Mark all read button
        self._mark_all_btn = ft.ElevatedButton(
            text=_("全部已读"),
            icon=ft.Icons.DONE_ALL,
            on_click=self._mark_all_read,
        )

        toolbar = ft.Row([
            self._filter_chips,
            ft.Container(expand=True),
            self._mark_all_btn,
        ])

        # Notification list
        self._notif_list = ft.ListView(expand=True, spacing=4)

        self.content = ft.Container(
            content=ft.Column([
                ft.Row([header]),
                ft.Row([toolbar]),
                ft.Divider(height=2, color=CARD_BORDER),
                self._notif_list,
            ]),
            padding=10,
        )

        self._load()

    def _on_filter(self, category: str, e):
        self._filter_category = category
        # Update chip selection
        for chip in self._filter_chips.controls:
            chip.selected = (chip.label.value == CATEGORY_LABELS[category])
        self._load()

    def _mark_all_read(self, e):
        self._nc.mark_all_read()
        self._load()
        if hasattr(self.app, 'update_unread_badge'):
            self.app.update_unread_badge()

    def _load(self):
        notifications = self._nc.get_all(
            limit=50,
            category=None if self._filter_category == "all" else self._filter_category,
        )
        self._notif_list.controls.clear()

        if not notifications:
            self._notif_list.controls.append(
                ft.Text(_("暂无通知"), color=TEXT_SECONDARY, size=14)
            )
        else:
            for n in notifications:
                icon = LEVEL_ICONS.get(n.level, ft.Icons.INFO)
                color = LEVEL_COLORS.get(n.level, ft.Colors.BLUE)
                read_opacity = 0.5 if n.read else 1.0
                cat_label = CATEGORY_LABELS.get(n.category, n.category)
                ts = n.timestamp[:16] if n.timestamp else ""

                row = ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, color=color, size=18),
                        ft.Column([
                            ft.Text(n.title, weight=ft.FontWeight.BOLD if not n.read else None,
                                    size=13, color=TEXT_PRIMARY),
                            ft.Text(n.message[:80], size=12, color=TEXT_SECONDARY),
                            ft.Text(f"[{cat_label}] {ts}", size=10, color=TEXT_SECONDARY),
                        ], spacing=2, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CHECK_CIRCLE_OUTLINE if n.read else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            on_click=lambda e, nid=n.id: self._mark_read(nid),
                            tooltip=_("标记已读"),
                            icon_size=18,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                    padding=8,
                    border_radius=8,
                    bgcolor=CARD_BG,
                    opacity=read_opacity,
                    on_click=lambda e, n=n: self._on_notif_click(n),
                )
                self._notif_list.controls.append(row)

        try:
            self._notif_list.update()
        except RuntimeError:
            pass

    def _mark_read(self, nid: str):
        self._nc.mark_read(nid)
        self._load()
        if hasattr(self.app, 'update_unread_badge'):
            self.app.update_unread_badge()

    def _on_notif_click(self, n: Notification):
        """Mark as read on click."""
        if not n.read:
            self._nc.mark_read(n.id)
            self._load()
            if hasattr(self.app, 'update_unread_badge'):
                self.app.update_unread_badge()
