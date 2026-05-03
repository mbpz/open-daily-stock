"""Flet GUI 应用主类"""
import flet as ft

from gui.theme import PRIMARY_COLOR, TEXT_PRIMARY, TEXT_SECONDARY

VERSION = "0.2.1"
from src.service_client import ServiceClient
from tui.data.task_store import TaskStore
from src.config import get_config
from src.core.pipeline import StockAnalysisPipeline


class StockApp:
    """Stock Analysis GUI Application with NavigationRail"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Stock Analysis"
        self.page.bgcolor = PRIMARY_COLOR

        self.nav_index = 0
        self.status_text = "最后更新"

        # Initialize ServiceClient for DataService communication
        self._client = ServiceClient()

        # Initialize task store
        self._task_store = TaskStore()

        self._build_ui()
        self._load_page("markets")

    def _build_ui(self):
        """Build the main UI layout"""
        # Navigation rail
        self.nav_rail = ft.NavigationRail(
            selected_index=self.nav_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.SHOW_CHART,
                    label="K线"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.CANDLESTICK_CHART,
                    label="行情"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ANALYTICS,
                    label="分析"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.HISTORY,
                    label="任务"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS,
                    label="配置"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.DESCRIPTION,
                    label="日志"
                ),
            ],
            on_change=self._on_nav_change,
        )

        # Status bar with version and update button
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Text(f"最后更新: {self.status_text}", color=TEXT_SECONDARY, size=14),
                ft.Container(expand=True),
                ft.Text(f"v{VERSION}", color=TEXT_SECONDARY, size=12),
                ft.IconButton(
                    icon=ft.Icons.UPDATE,
                    on_click=self._check_update,
                    tooltip="检查更新",
                ),
            ]),
            padding=10,
            bgcolor=PRIMARY_COLOR,
            on_click=self._install_update,
        )

        # Content area
        self.content_area = ft.Container(
            content=ft.Text("Loading...", color=TEXT_PRIMARY),
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

    def _on_nav_change(self, e):
        """Handle navigation rail selection change"""
        page_names = ["chart", "markets", "analyze", "tasks", "config", "logs"]
        self.nav_index = e.control.selected_index
        self._load_page(page_names[self.nav_index])

    def _load_page(self, page_name: str):
        """Load and display the specified page"""
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
                f"Unknown page: {page_name}",
                color=ft.colors.RED
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
                    f"Failed to load {page_name} page",
                    color=ft.colors.RED,
                    size=16,
                ),
                ft.Text(
                    str(ex),
                    color=ft.colors.GREY,
                    size=12,
                ),
            ])
            self.page.update()

    def update_status(self, text: str):
        """Update the status bar text"""
        self.status_text = text
        self.status_bar.content = ft.Row([
            ft.Text(f"最后更新: {self.status_text}", color=TEXT_SECONDARY, size=14),
            ft.Container(expand=True),
            ft.Text(f"v{VERSION}", color=TEXT_SECONDARY, size=12),
            ft.IconButton(
                icon=ft.Icons.UPDATE,
                on_click=self._check_update,
                tooltip="检查更新",
            ),
        ])
        self.status_bar.update()

    def _check_update(self, e):
        """Check for application updates"""
        from src.update_service import UpdateService
        latest, url = UpdateService.check_latest_version()
        if latest:
            self.update_status(f"发现新版本 {latest}，点击更新")
            self._pending_update_url = url
        else:
            self.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"已是最新版本 v{VERSION}"), open=True)
            )

    def _install_update(self, e):
        """Download and install pending update"""
        if hasattr(self, '_pending_update_url') and self._pending_update_url:
            url = self._pending_update_url
            self.update_status("正在下载更新...")
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
                self.update_status("更新完成，重启应用")
            else:
                self.update_status("更新失败")
        except Exception as ex:
            self.update_status(f"更新失败: {ex}")