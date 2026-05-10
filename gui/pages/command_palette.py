"""P5-7: Command Palette — GUI (Flet) overlay with fuzzy search.

Triggered by Ctrl+K, this overlay dialog lets users search and execute any
registered command without navigating through tabs.
"""

from __future__ import annotations
import flet as ft
from typing import List, Dict, Any, Optional

from src.shared.commands import (
    Command, CATEGORY_META,
    search_commands as fuzzy_match,
    get_recent_commands, execute_command, record_recent_command,
    get_command_registry,
)


class CommandPaletteOverlay:
    """Flet-based command palette overlay for the GUI.

    Managed as a "floating" container that is added/removed from page.overlay.
    """

    def __init__(self, app):
        self._app = app
        self._page: ft.Page = app.page
        self._results: List[Any] = []  # List of dict or Command
        self._selected_idx: int = 0
        self._is_open: bool = False
        self._search_field: Optional[ft.TextField] = None
        self._results_list: Optional[ft.Column] = None
        self._container: Optional[ft.Container] = None

    @staticmethod
    def _cmd_id(cmd: Any) -> str:
        """Get command ID from dict or Command object."""
        if isinstance(cmd, Command):
            return cmd.id
        return cmd.get("id", "")

    @staticmethod
    def _cmd_label(cmd: Any) -> str:
        """Get command label/name from dict or Command object."""
        if isinstance(cmd, Command):
            return cmd.name
        return cmd.get("label", "")

    @staticmethod
    def _cmd_category(cmd: Any) -> str:
        """Get command category from dict or Command object."""
        if isinstance(cmd, Command):
            return cmd.category
        return cmd.get("category", "")

    @staticmethod
    def _cmd_keywords(cmd: Any) -> List[str]:
        """Get command keywords from dict or Command object."""
        if isinstance(cmd, Command):
            return cmd.keywords
        return cmd.get("keywords", [])

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self):
        """Show the command palette."""
        if self._is_open:
            return

        self._is_open = True
        self._selected_idx = 0

        # Show initial results (recent or all)
        recent = get_recent_commands()
        if recent:
            self._results = recent
        else:
            self._results = list(get_command_registry().values())

        self._build_ui()
        if self._container is None:
            return
        self._page.overlay.append(self._container)
        self._page.update()
        self._search_field.focus()

    def close(self):
        """Dismiss the command palette."""
        if not self._is_open:
            return
        self._is_open = False
        if self._container in self._page.overlay:
            self._page.overlay.remove(self._container)
        self._page.update()

    def _build_ui(self):
        """Construct the overlay UI."""
        theme = self._app._theme if hasattr(self._app, '_theme') else "dark"
        is_dark = theme == "dark"

        bg_color = ft.Colors.GREY_900 if is_dark else ft.Colors.WHITE
        border_color = ft.Colors.GREEN_500 if is_dark else ft.Colors.GREEN_800
        input_bg = ft.Colors.GREY_800 if is_dark else ft.Colors.GREY_100
        input_fg = ft.Colors.WHITE if is_dark else ft.Colors.BLACK
        text_primary = ft.Colors.WHITE if is_dark else ft.Colors.BLACK
        text_secondary = ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600
        accent = ft.Colors.GREEN_400 if is_dark else ft.Colors.GREEN_700

        # Search field
        self._search_field = ft.TextField(
            hint_text="搜索命令... (支持中文/英文)",
            autofocus=True,
            border_color=accent,
            bgcolor=input_bg,
            color=input_fg,
            on_change=self._on_search,
            on_submit=self._on_submit,
            text_size=14,
            prefix_icon=ft.Icons.SEARCH,
        )

        # Results list
        self._results_list = ft.Column(
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            height=350,
        )
        self._refresh_results_display()

        # Hint bar
        hint_row = ft.Row([
            ft.Text("↑↓ 导航  Enter 执行  Esc 关闭", size=11, color=text_secondary),
            ft.Container(expand=True),
            ft.Text("Ctrl+K", size=11, color=text_secondary),
        ])

        # Main content
        content = ft.Column([
            ft.Row([
                ft.Text("Command Palette", size=16, weight=ft.FontWeight.BOLD, color=text_primary),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_color=text_secondary,
                    on_click=lambda e: self.close(),
                    icon_size=18,
                ),
            ]),
            ft.Divider(height=1, color=border_color),
            self._search_field,
            ft.Container(
                content=self._results_list,
                expand=True,
            ),
            hint_row,
        ], spacing=8)

        self._container = ft.Container(
            content=ft.Card(
                content=ft.Container(
                    content=content,
                    padding=20,
                    bgcolor=bg_color,
                    border_radius=12,
                    width=600,
                ),
                elevation=20,
                color=border_color,
            ),
            alignment=ft.alignment.center,
            on_click=self._on_backdrop_click,
            bgcolor=ft.Colors.BLACK54,
            width=self._page.width,
            height=self._page.height,
            left=0,
            top=0,
        )

    def _on_backdrop_click(self, e):
        """Close when clicking outside the card (the backdrop)."""
        self.close()

    def _build_result_row(self, cmd: Any, is_selected: bool) -> ft.Container:
        """Build a single result row."""
        theme = self._app._theme if hasattr(self._app, '_theme') else "dark"
        is_dark = theme == "dark"
        accent = ft.Colors.GREEN_400 if is_dark else ft.Colors.GREEN_700
        text_secondary = ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600
        row_bg = ft.Colors.GREY_800 if is_dark else ft.Colors.GREY_100

        cat = self._cmd_category(cmd)
        meta = CATEGORY_META.get(cat, {})
        icon = meta.get("icon", "  ")
        short = meta.get("short", "???")

        # Highlight selected row
        bg = accent if is_selected else row_bg
        name_color = ft.Colors.WHITE if is_selected and is_dark else accent
        name_color = ft.Colors.BLACK if is_selected and not is_dark else name_color

        label = self._cmd_label(cmd)
        keywords = ", ".join(self._cmd_keywords(cmd)[:3])

        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(f"{icon} [{short}]", size=12, color=text_secondary),
                    width=80,
                ),
                ft.Text(label, size=14, weight=ft.FontWeight.BOLD, color=name_color, width=120),
                ft.Text(keywords, size=12, color=text_secondary),
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            bgcolor=bg,
            border_radius=6,
            on_click=lambda e, c=cmd: self._execute(c),
        )

    def _refresh_results_display(self):
        """Rebuild the results column."""
        if self._results_list is None:
            return
        self._results_list.controls.clear()

        if not self._results:
            self._results_list.controls.append(
                ft.Container(
                    content=ft.Text("无匹配结果", size=13, italic=True, color=ft.Colors.GREY_500),
                    padding=ft.padding.only(top=20, left=10),
                )
            )
            return

        for i, cmd in enumerate(self._results):
            row = self._build_result_row(cmd, is_selected=(i == self._selected_idx))
            self._results_list.controls.append(row)

    def _on_search(self, e):
        """Handle search input changes."""
        query = (e.control.value or "").strip()
        if not query:
            recent = get_recent_commands()
            if recent:
                self._results = recent
            else:
                self._results = list(get_command_registry().values())
        else:
            self._results = search_commands(query)

        self._selected_idx = 0
        self._refresh_results_display()
        if hasattr(self._results_list, 'update'):
            self._results_list.update()

    def _on_submit(self, e):
        """Handle Enter press on search field."""
        if self._results and self._selected_idx < len(self._results):
            self._execute(self._results[self._selected_idx])

    def _execute(self, cmd: Any):
        """Execute the selected command."""
        cmd_id = self._cmd_id(cmd)

        # Record as recently used
        record_recent_command(cmd_id)

        # Handle navigation commands (dot-format IDs from shared registry)
        nav_map = {
            "nav.markets": 1,
            "nav.analyze": 2,
            "nav.tasks": 3,
            "nav.config": 4,
            "nav.logs": 5,
            "nav.strategies": 6,
        }

        if cmd_id in nav_map:
            idx = nav_map[cmd_id]
            if hasattr(self._app, 'nav_rail'):
                self._app.nav_rail.selected_index = idx
                self._app.nav_index = idx
                page_names = ["chart", "markets", "analyze", "tasks", "config", "logs", "strategies"]
                self._app._load_page(page_names[idx])
            execute_command(cmd_id, self._app)
            self.close()
            return

        # Theme toggle
        if cmd_id == "config.theme_toggle":
            self._app._toggle_theme(None)
            execute_command(cmd_id, self._app)
            self.close()
            return

        # Market refresh
        if cmd_id == "markets.refresh":
            execute_command(cmd_id, self._app)
            self.close()
            return

        # Strategy commands → navigate to strategies tab
        if cmd_id in ("strategies.list", "strategies.import",
                       "strategies.export", "backtest.run"):
            if hasattr(self._app, 'nav_rail'):
                self._app.nav_rail.selected_index = 6
                self._app.nav_index = 6
                self._app._load_page("strategies")
            execute_command(cmd_id, self._app)
            self.close()
            return

        # Screener / Financials → navigate to analysis tab
        if cmd_id in ("screener.open", "financials.open", "analyze.quick",
                       "analyze.deep", "analyze.stream"):
            if hasattr(self._app, 'nav_rail'):
                self._app.nav_rail.selected_index = 2
                self._app.nav_index = 2
                self._app._load_page("analyze")
            execute_command(cmd_id, self._app)
            self.close()
            return

        # Generic handler dispatch
        executed = execute_command(cmd_id, self._app)
        if not executed:
            label = self._cmd_label(cmd)
            self._page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text(f"命令 '{label}' 已触发"),
                    open=True,
                )
            )
        self.close()

    def select_next(self):
        """Select the next result (for keyboard nav)."""
        if self._results:
            self._selected_idx = (self._selected_idx + 1) % len(self._results)
            self._refresh_results_display()
            if hasattr(self._results_list, 'update'):
                self._results_list.update()

    def select_prev(self):
        """Select the previous result (for keyboard nav)."""
        if self._results:
            self._selected_idx = (self._selected_idx - 1) % len(self._results)
            self._refresh_results_display()
            if hasattr(self._results_list, 'update'):
                self._results_list.update()
