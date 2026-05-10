"""GUI toast notifications using Flet SnackBar and overlay."""
import flet as ft
from src.notification_center import Notification

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


def show_toast(page: ft.Page, notification: Notification, dismiss_seconds: float = 5.0):
    """Show a SnackBar toast for a notification."""
    bg = LEVEL_COLORS.get(notification.level, ft.Colors.BLUE)
    icon = LEVEL_ICONS.get(notification.level, ft.Icons.INFO)
    content_text = f"{notification.title}"
    if notification.message:
        content_text += f": {notification.message[:60]}"
    snack = ft.SnackBar(
        content=ft.Row([
            ft.Icon(icon, color=ft.Colors.WHITE),
            ft.Text(content_text, color=ft.Colors.WHITE),
        ]),
        bgcolor=bg,
        duration=int(dismiss_seconds * 1000),
        show_close_icon=True,
        on_click=lambda e: setattr(notification, 'read', True),
    )
    page.open(snack)
