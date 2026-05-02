"""日志页面"""
import flet as ft
from pathlib import Path
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY

class LogsPage(ft.UserControl):
    """日志查看页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        header = ft.Text("运行日志", size=24, weight=ft.FontWeight.BOLD)

        toolbar = ft.Row([
            ft.IconButton(
                icon=ft.icons.REFRESH,
                on_click=self._load_logs,
                tooltip="刷新",
            ),
        ])

        self._log_content = ft.Container(
            content=ft.Text("加载中...", color=TEXT_SECONDARY),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self._load_logs(None)

        return ft.Container(
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
                        self._log_content.content = ft.Text(
                            f"权限不足: {latest_log}", color="#f44336"
                        )
                        self._log_content.update()
                        return
                    lines = content.split("\n")[-100:]
                    display = "\n".join(lines)
                    self._log_content.content = ft.Text(
                        display, size=11, font_family="monospace"
                    )
                else:
                    self._log_content.content = ft.Text(
                        "暂无日志", color=TEXT_SECONDARY
                    )
            else:
                self._log_content.content = ft.Text(
                    "日志目录不存在", color=TEXT_SECONDARY
                )
        except Exception as ex:
            self._log_content.content = ft.Text(
                f"加载失败: {ex}", color="#f44336"
            )
        self._log_content.update()