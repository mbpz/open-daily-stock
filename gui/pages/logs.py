"""日志页面"""
import flet as ft
from pathlib import Path
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY
from src.i18n import _

class LogsPage(ft.Container):
    """日志查看页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._filter_level = "all"
        self._search_query = ""

        header = ft.Text(_("运行日志"), size=24, weight=ft.FontWeight.BOLD)

        self._search_field = ft.TextField(
            hint_text=_("搜索日志..."),
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
            expand=True,
        )

        self._level_dropdown = ft.Dropdown(
            label=_("级别"),
            value="all",
            width=120,
            options=[
                ft.dropdown.Option("all", _("全部")),
                ft.dropdown.Option("info", "INFO"),
                ft.dropdown.Option("warning", "WARNING"),
                ft.dropdown.Option("error", "ERROR"),
            ],
            on_select=self._on_level_change,
        )

        toolbar = ft.Row([
            self._search_field,
            self._level_dropdown,
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                on_click=self._load_logs,
                tooltip=_("刷新"),
            ),
        ])

        self._log_content = ft.ListView(
            expand=True,
            spacing=10,
        )
        self._log_text = ft.Text(_("加载中..."), color=TEXT_SECONDARY)
        self._log_content.controls.append(self._log_text)

        self._load_logs(None)

        self.content = ft.Container(
            content=ft.Column([
                ft.Row([header]),
                ft.Row([toolbar]),
                ft.Divider(height=2, color=CARD_BORDER),
                self._log_content,
            ]),
            padding=10,
        )

    def _on_search_change(self, e):
        self._search_query = e.control.value.lower()
        self._load_logs(None)

    def _on_level_change(self, e):
        self._filter_level = e.control.value
        self._load_logs(None)

    def _load_logs(self, e):
        """加载日志"""
        try:
            log_dir = Path("./logs")
            display_lines = []
            if log_dir.exists():
                log_files = sorted(log_dir.glob("stock_analysis_*.log"))
                if log_files:
                    latest_log = log_files[-1]
                    try:
                        content = latest_log.read_text(encoding="utf-8")
                    except PermissionError:
                        self._log_text.value = f"权限不足: {latest_log}"
                        self._log_text.color = "#f44336"
                        try:
                            self._log_content.update()
                        except RuntimeError:
                            pass
                        return
                    for line in content.split("\n")[-100:]:
                        level = self._filter_level
                        if level != "all" and level not in line.lower():
                            continue
                        if self._search_query and self._search_query not in line.lower():
                            continue
                        display_lines.append(line)
                    display = "\n".join(display_lines) if display_lines else _("暂无日志")
                    self._log_text.value = display
                    self._log_text.size = 11
                    self._log_text.font_family = "monospace"
                    self._log_text.color = TEXT_SECONDARY
                else:
                    self._log_text.value = _("暂无日志")
                    self._log_text.color = TEXT_SECONDARY
            else:
                self._log_text.value = _("日志目录不存在")
                self._log_text.color = TEXT_SECONDARY
        except Exception as ex:
            self._log_text.value = f"{_('加载失败: ')}{ex}"
            self._log_text.color = "#f44336"
        try:
            self._log_content.update()
        except RuntimeError:
            pass