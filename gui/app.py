"""Flet GUI 应用主类"""
import sys
import importlib
import flet as ft

from gui.theme import get_theme, set_theme as apply_theme, get_current_theme_name
from src.i18n import _

VERSION = "0.2.1"
from src.service_client import ServiceClient
from tui.data.task_store import TaskStore
from src.config import get_config


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

        # Initialize ServiceClient for DataService communication
        self._client = ServiceClient()

        # Initialize task store
        self._task_store = TaskStore()

        self._build_ui()
        self._load_page("markets")

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

        # Status bar with version, theme toggle, and update button
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Text(f"{_('last_update')}: {self.status_text}",
                        color=theme["TEXT_SECONDARY"], size=14),
                ft.Container(expand=True),
                self._theme_btn,
                ft.Text(f"v{VERSION}", color=theme["TEXT_SECONDARY"], size=12),
                ft.IconButton(
                    icon=ft.Icons.UPDATE,
                    on_click=self._check_update,
                    tooltip=_("check_update"),
                ),
            ]),
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
                except Exception:
                    pass

        # Update page background
        self.page.bgcolor = theme["PRIMARY_COLOR"]

        # Update theme button
        self._theme_btn.icon = ft.Icons.LIGHT_MODE if new_theme == "dark" else ft.Icons.DARK_MODE
        self._theme_btn.tooltip = _("切换到亮色主题") if new_theme == "dark" else _("切换到暗色主题")

        # Update status bar
        self._update_status_bar()

        # Reload current page with new theme
        page_names = ["chart", "markets", "analyze", "tasks", "config", "logs"]
        current_page = page_names[self.nav_index] if self.nav_index < len(page_names) else "markets"
        self._load_page(current_page)

        self.page.update()

    def _update_status_bar(self):
        """Update status bar to reflect current theme"""
        theme = get_theme()
        self.status_bar.content = ft.Row([
            ft.Text(f"{_('last_update')}: {self.status_text}",
                    color=theme["TEXT_SECONDARY"], size=14),
            ft.Container(expand=True),
            self._theme_btn,
            ft.Text(f"v{VERSION}", color=theme["TEXT_SECONDARY"], size=12),
            ft.IconButton(
                icon=ft.Icons.UPDATE,
                on_click=self._check_update,
                tooltip=_("check_update"),
            ),
        ])
        self.status_bar.bgcolor = theme["PRIMARY_COLOR"]
        self.status_bar.update()

    def _on_nav_change(self, e):
        """Handle navigation rail selection change"""
        page_names = ["chart", "markets", "analyze", "tasks", "config", "logs"]
        self.nav_index = e.control.selected_index
        self._load_page(page_names[self.nav_index])

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
        }
        class_map = {
            "chart": "ChartPage",
            "markets": "MarketsPage",
            "analyze": "AnalyzePage",
            "tasks": "TasksPage",
            "config": "ConfigPage",
            "logs": "LogsPage",
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
        from src.update_service import UpdateService
        latest, url = UpdateService.check_latest_version()
        if latest:
            self.update_status(f"{_('new_version')} {latest}，{_('click_to_update')}")
            self._pending_update_url = url
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
