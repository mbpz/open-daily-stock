"""Flet GUI 应用主类"""
import asyncio
import threading
import importlib
import logging
import sys
import flet as ft

logger = logging.getLogger(__name__)

from gui.theme import get_theme, set_theme as apply_theme, get_current_theme_name
from src.i18n import _
from src.notification_center import get_notification_center, Notification

from src.update_checker import UpdateChecker

VERSION = "0.2.1"
from src.service_client import ServiceClient  # noqa: F401  (re-imported lazily in _start_backend)
from gui.data.task_store import TaskStore
from src.config import get_config
from typing import Optional


class StockApp:
    """Stock Analysis GUI Application with NavigationRail"""

    def __init__(self, page: ft.Page):
        self.page = page
        config = get_config()

        # 从 config.json 读取主题
        self._theme = config.theme or "dark"
        apply_theme(self._theme)

        self.page.title = _("stock_analysis")
        theme = get_theme()
        self.page.bgcolor = theme["PRIMARY_COLOR"]

        # 读取按键配置（用于 tooltip 显示）
        self._keybindings = config.keybindings if config.keybindings else {}

        self.nav_index = 0
        self.status_text = _("last_update")

        # Backend service client. Created lazily and started in the
        # background so a slow DataService spawn never blocks the UI.
        # Until the handshake completes, page modules fall back to a
        # local-only mode (see self._client_available).
        self._client: Optional["ServiceClient"] = None
        self._client_available = False
        # Two locks because get_client() is called from sync Flet callbacks
        # that may run on different threads, while _start_backend runs on
        # the asyncio event loop. Both serialize the spawn path.
        self._client_lock = asyncio.Lock()       # async path
        self._client_thread_lock = threading.Lock()  # sync path

        # Pipeline reference (lazy-init; used by analyze page as fallback)
        self._pipeline = None

        # Initialize task store
        self._task_store = TaskStore()

        # P5-7: Command palette overlay (lazy-init)
        self._command_palette = None

        # Update checker (background check scheduled below)
        self._update_checker = UpdateChecker(current_version=VERSION)

        # Global keyboard handler for Ctrl+K
        self.page.on_keyboard_event = self._on_keyboard

        # Check for updates on startup if enabled (non-blocking)
        self.page.run_task(self._check_update_on_startup_async)

        # Notification center
        self._nc = get_notification_center()
        self._nc.add_listener(self._on_notification)

        self._build_ui()
        # Always load the markets page immediately; the page itself will
        # show a placeholder while the backend handshake is in flight.
        self._load_page("markets")

        # Kick off async backend startup AFTER the first frame so the user
        # sees the UI before we block on subprocess.spawn / IPC handshake.
        self.page.run_task(self._start_backend)

    BACKEND_START_TIMEOUT = 8.0  # seconds

    async def _start_backend(self) -> None:
        """Spawn the DataService subprocess and complete the IPC handshake.

        All work runs in a worker thread so the Flet event loop is never
        blocked. On failure, the UI shows a snackbar with a retry button
        and the rest of the app continues to function in offline mode
        (pages that need the backend will report a friendly error).
        """
        from src.service_client import ServiceClient, ServiceClientError

        self.update_status("正在启动后端服务...")
        try:
            self._client = await asyncio.to_thread(self._spawn_and_handshake)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"DataService 启动失败: {e}")
            self._client = None
            self._client_available = False
            self._show_backend_error(str(e))
            return

        self._client_available = True
        # Refresh the markets page so it picks up the now-available client.
        # Guard with getattr so this is robust to test harnesses that
        # instantiate StockApp without running the full __init__.
        nav_index = getattr(self, "nav_index", 0)
        if nav_index == 1:  # markets page index
            self._load_page("markets")
        if hasattr(self, "update_status"):
            self.update_status(_("last_update"))

    def _spawn_and_handshake(self):
        """Synchronous helper: spawn DataService and complete the hello handshake."""
        from src.service_client import ServiceClient, ServiceClientError

        client = ServiceClient()
        # hello() is the first real IPC; if it fails we want to surface that
        # immediately rather than letting the user hit it on a stock action.
        client.hello()
        return client

    def _show_backend_error(self, message: str) -> None:
        """Display a non-blocking error banner with a retry button."""
        theme = get_theme()
        try:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.WHITE),
                        ft.Text(
                            f"后端服务启动失败: {message[:80]}",
                            color=ft.Colors.WHITE,
                            expand=True,
                        ),
                        ft.TextButton(
                            "重试",
                            on_click=lambda _e: self.page.run_task(self._start_backend),
                        ),
                    ],
                    tight=True,
                ),
                bgcolor=theme["ERROR_COLOR"],
                open=True,
                duration=10,
            )
            self.page.update()
        except Exception:
            logger.warning("显示后端错误 snackbar 失败")

    def get_client(self):
        """Return the ServiceClient, spawning it on demand if necessary.

        Thread-safe: Flet invokes this from many callback threads. Uses
        a threading.Lock with double-checked locking so concurrent
        callers see a single shared client instance.
        """
        if self._client is not None and self._client_available:
            return self._client
        with self._client_thread_lock:
            # Re-check under the lock to avoid duplicate spawns.
            if self._client is not None and self._client_available:
                return self._client
            from src.service_client import ServiceClient, ServiceClientError
            try:
                client = ServiceClient()
                client.hello()
                self._client = client
                self._client_available = True
            except ServiceClientError as e:
                logger.warning(f"按需启动后端失败: {e}")
                return None
        return self._client

    def _build_ui(self):
        """Build the main UI layout"""
        theme = get_theme()

        # Navigation rail
        self.nav_rail = ft.NavigationRail(
            selected_index=self.nav_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.SHOW_CHART,
                    label=_("chart")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.CANDLESTICK_CHART,
                    label=_("markets")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ANALYTICS,
                    label=_("analyze")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.HISTORY,
                    label=_("tasks")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS,
                    label=_("config")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.DESCRIPTION,
                    label=_("logs")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.STRATEGY,
                    label=_("strategies")
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.NOTIFICATIONS,
                    label=_("通知中心")
                ),
            ],
            on_change=self._on_nav_change,
        )

        # Theme toggle button
        theme_icon = ft.Icons.LIGHT_MODE if self._theme == "dark" else ft.Icons.DARK_MODE
        theme_tooltip = _("切换到亮色主题") if self._theme == "dark" else _("切换到暗色主题")
        self._theme_btn = ft.IconButton(
            icon=theme_icon,
            on_click=self._toggle_theme,
            tooltip=theme_tooltip,
        )

        # Demo mode badge (P5-4)
        self._demo_badge = None
        config = get_config()
        if config.is_demo_mode():
            self._demo_badge = ft.Container(
                content=ft.Text("演示模式", color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.BOLD),
                bgcolor=theme["WARNING_COLOR"],
                border_radius=4,
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                tooltip="配置 API key 后解锁实时 AI 分析",
            )

        # Status bar with version, theme toggle, demo badge, notification bell, and update button
        self._notif_bell = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_OUTLINED,
            on_click=self._open_notifications,
            tooltip=_("通知中心"),
        )
        status_controls = [
            ft.Text(f"{_('last_update')}: {self.status_text}",
                    color=theme["TEXT_SECONDARY"], size=14),
            ft.Container(expand=True),
        ]
        if self._demo_badge:
            status_controls.append(self._demo_badge)
            status_controls.append(ft.Container(width=8))
        status_controls.extend([
            self._notif_bell,
            self._theme_btn,
            ft.Text(f"v{VERSION}", color=theme["TEXT_SECONDARY"], size=12),
            ft.IconButton(
                icon=ft.Icons.UPDATE,
                on_click=self._check_update,
                tooltip=_("check_update"),
            ),
        ])

        self.update_unread_badge()

        self.status_bar = ft.Container(
            content=ft.Row(status_controls),
            padding=10,
            bgcolor=theme["PRIMARY_COLOR"],
            on_click=self._install_update,
        )

        # Content area
        self.content_area = ft.Container(
            content=ft.Text(_("loading"), color=theme["TEXT_PRIMARY"]),
            expand=True,
            padding=20,
        )

        # Main layout with row
        main_row = ft.Row(
            controls=[
                self.nav_rail,
                ft.VerticalDivider(width=1, color=ft.colors.GREY_800),
                self.content_area,
            ],
            expand=True,
        )

        self.page.add(self.status_bar)
        self.page.add(main_row)

    def _toggle_theme(self, e):
        """Toggle between dark and light theme"""
        new_theme = "light" if self._theme == "dark" else "dark"
        self._theme = new_theme
        theme = apply_theme(new_theme)

        # 持久化到 config.json
        config = get_config()
        config.theme = new_theme
        config.save_json_config({"theme": new_theme})

        # Reload all page modules so their `from gui.theme import X` picks up new theme
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("gui.pages."):
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception as e:
                    logger.warning(f"Failed to reload module {mod_name}: {e}")

        # Update page background
        self.page.bgcolor = theme["PRIMARY_COLOR"]

        # Update theme button
        self._theme_btn.icon = ft.Icons.LIGHT_MODE if new_theme == "dark" else ft.Icons.DARK_MODE
        self._theme_btn.tooltip = _("切换到亮色主题") if new_theme == "dark" else _("切换到暗色主题")

        # Update status bar
        self._update_status_bar()

        # Reload current page with new theme
        page_names = ["chart", "markets", "analyze", "tasks", "config", "logs", "strategies", "notifications"]
        current_page = page_names[self.nav_index] if self.nav_index < len(page_names) else "markets"
        self._load_page(current_page)

        self.page.update()

    def _update_status_bar(self):
        """Update status bar to reflect current theme"""
        theme = get_theme()
        status_controls = [
            ft.Text(f"{_('last_update')}: {self.status_text}",
                    color=theme["TEXT_SECONDARY"], size=14),
            ft.Container(expand=True),
        ]
        if self._demo_badge:
            status_controls.append(self._demo_badge)
            status_controls.append(ft.Container(width=8))
        status_controls.extend([
            self._notif_bell,
            self._theme_btn,
            ft.Text(f"v{VERSION}", color=theme["TEXT_SECONDARY"], size=12),
            ft.IconButton(
                icon=ft.Icons.UPDATE,
                on_click=self._check_update,
                tooltip=_("check_update"),
            ),
        ])
        self.status_bar.content = ft.Row(status_controls)
        self.status_bar.bgcolor = theme["PRIMARY_COLOR"]
        self.status_bar.update()

    def _open_notifications(self, e):
        """Open the notifications page."""
        self._load_page("notifications")

    def _on_notification(self, notification: Notification):
        """Handle incoming notification -- show toast in GUI."""
        try:
            from gui.pages.toast import show_toast
            show_toast(self.page, notification)
        except Exception:
            pass
        self.update_unread_badge()

    def update_unread_badge(self):
        """Update notification bell badge."""
        try:
            count = self._nc.get_unread_count()
            if count > 0:
                self._notif_bell.icon = ft.Icons.NOTIFICATIONS_ACTIVE
                self._notif_bell.tooltip = f"通知({count})"
            else:
                self._notif_bell.icon = ft.Icons.NOTIFICATIONS_OUTLINED
                self._notif_bell.tooltip = "通知中心"
            self._notif_bell.update()
        except Exception:
            pass

    def _on_nav_change(self, e):
        """Handle navigation rail selection change"""
        page_names = ["chart", "markets", "analyze", "tasks", "config", "logs", "strategies", "notifications"]
        self.nav_index = e.control.selected_index
        self._load_page(page_names[self.nav_index])

    def _on_keyboard(self, e: ft.KeyboardEvent):
        """P5-7: Global keyboard handler for Ctrl+K command palette and arrow navigation."""
        if e.ctrl and e.key.lower() == "k":
            self._open_command_palette()
            return

        # Arrow key navigation within command palette
        if self._command_palette and self._command_palette.is_open:
            if e.key == "Arrow Down":
                self._command_palette.select_next()
            elif e.key == "Arrow Up":
                self._command_palette.select_prev()
            elif e.key == "Escape":
                self._command_palette.close()

    def _open_command_palette(self):
        """Open or toggle the command palette overlay."""
        from gui.pages.command_palette import CommandPaletteOverlay
        if self._command_palette and self._command_palette.is_open:
            self._command_palette.close()
            return
        self._command_palette = CommandPaletteOverlay(self)
        self._command_palette.open()

    def _load_page(self, page_name: str):
        """Load and display the specified page"""
        theme = get_theme()

        page_map = {
            "chart": "gui.pages.chart",
            "markets": "gui.pages.markets",
            "analyze": "gui.pages.analyze",
            "tasks": "gui.pages.tasks",
            "config": "gui.pages.config",
            "logs": "gui.pages.logs",
            "strategies": "gui.pages.strategies",
            "notifications": "gui.pages.notifications",
        }
        class_map = {
            "chart": "ChartPage",
            "markets": "MarketsPage",
            "analyze": "AnalyzePage",
            "tasks": "TasksPage",
            "config": "ConfigPage",
            "logs": "LogsPage",
            "strategies": "StrategiesPage",
            "notifications": "NotificationsPage",
        }

        if page_name not in page_map:
            self.content_area.content = ft.Text(
                f"{_('unknown_page')}: {page_name}",
                color=theme["ERROR_COLOR"]
            )
            self.page.update()
            return

        try:
            module = __import__(page_map[page_name], fromlist=[class_map[page_name]])
            page_class = getattr(module, class_map[page_name])
            # Pass data provider to pages that need it
            if page_name == "chart":
                self.content_area.content = page_class(self, self._client)
            elif page_name == "markets":
                self.content_area.content = page_class(self, self._client)
            elif page_name == "analyze":
                self.content_area.content = page_class(self, self._pipeline)
            elif page_name == "tasks":
                self.content_area.content = page_class(self, self._task_store)
            else:
                self.content_area.content = page_class(self)
            self.page.update()
        except (ImportError, AttributeError) as ex:
            self.content_area.content = ft.Column([
                ft.Text(
                    f"{_('failed_to_load')} {page_name}",
                    color=theme["ERROR_COLOR"],
                    size=16,
                ),
                ft.Text(
                    str(ex),
                    color=theme["TEXT_MUTED"],
                    size=12,
                ),
            ])
            self.page.update()

    def update_status(self, text: str):
        """Update the status bar text"""
        self.status_text = text
        self._update_status_bar()

    def _check_update(self, e):
        """Check for application updates"""
        if self._update_checker.is_new_version_available():
            version, notes = self._update_checker.get_release_info()
            self._show_update_dialog(version, notes)
        else:
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('already_latest')} v{VERSION}"), open=True)
            )

    def _install_update(self, e):
        """Download and install pending update"""
        if hasattr(self, '_pending_update_url') and self._pending_update_url:
            url = self._pending_update_url
            self.update_status(_("downloading"))
            # Run download in background
            self.page.run_task(self._download_and_install, url)
        else:
            # Status bar click with no update available - run check
            self._check_update(e)

    async def _download_and_install(self, url: str):
        """Download and install update asynchronously"""
        from src.update_service import UpdateService
        try:
            success = UpdateService.download_and_install(url)
            if success:
                self.update_status(_("update_complete"))
            else:
                self.update_status(_("update_failed"))
        except Exception as ex:
            self.update_status(f"{_('update_failed')}: {ex}")

    async def _check_update_on_startup_async(self) -> None:
        """Check for updates if auto_check is enabled (runs in Flet loop)."""
        try:
            config = get_config()
            if not config.auto_check_update:
                return
            # Network-bound; offload to a worker thread.
            available = await asyncio.to_thread(self._update_checker.is_new_version_available)
            if not available:
                return
            version, notes = await asyncio.to_thread(self._update_checker.get_release_info)
            self._show_update_dialog(version, notes)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"启动时检查更新失败 (非致命): {e}")

    def _show_update_dialog(self, version, notes):
        """Show update dialog"""
        def on_download(e):
            import webbrowser
            webbrowser.open(f"https://github.com/mbpz/open-daily-stock/releases/tag/v{version}")
            self.page.dialog = None

        def on_ignore(e):
            self.page.dialog = None

        from gui.components.update_banner import UpdateDialog
        dialog = UpdateDialog(version, notes, on_download, on_ignore)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
