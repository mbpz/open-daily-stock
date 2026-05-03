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

        header = ft.Text(_("运行日志"), size=24, weight=ft.FontWeight.BOLD)

        toolbar = ft.Row([
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
                ft.Row([header, toolbar]),
                ft.Divider(height=2, color=CARD_BORDER),
                self._log_content,
            ]),
            padding=10,
        )

    def _load_logs(self, e):
        """加载日志"""
        try:
            log_dir = Path("./logs")
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
                    lines = content.split("\n")[-100:]
                    display = "\n".join(lines)
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