"""Update notification banner and dialog"""
import flet as ft
from typing import Optional

class UpdateBanner(ft.Container):
    """Banner shown when new version is available"""

    def __init__(self, app, version: str, notes: str, on_download, on_dismiss):
        super().__init__()
        self.app = app
        self.version = version
        self.notes = notes
        self.on_download = on_download
        self.on_dismiss = on_dismiss

        self.content = ft.Container(
            bgcolor="#2D1B69",  # dark purple
            padding=10,
            border_radius=8,
            content=ft.Row([
                ft.Icon(ft.Icons.UPDATE, color=ft.Colors.WHITE),
                ft.Text(f"发现新版本 {version}", color=ft.Colors.WHITE, expand=True),
                ft.TextButton("下载", on_click=self._on_download,
                              style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                ft.IconButton(ft.Icons.CLOSE, on_click=self._on_dismiss,
                              icon_color=ft.Colors.WHITE),
            ], alignment=ft.MainAxisAlignment.CENTER),
        )

    def _on_download(self, e):
        self.on_download(self.version)

    def _on_dismiss(self, e):
        self.on_dismiss(self.version)


class UpdateDialog(ft.AlertDialog):
    """Dialog shown first time a new version is detected"""

    def __init__(self, version: str, notes: str, on_download, on_ignore):
        super().__init__()
        self.modal = True
        self.title = ft.Text(f"发现新版本 v{version}")
        self.content = ft.Column([
            ft.Text("有可用更新，建议立即升级以获得最新功能。"),
            ft.Container(height=5),
            ft.Text(notes[:100] + "..." if len(notes) > 100 else notes,
                    size=12, color=ft.Colors.GREY_600),
        ])
        self.actions = [
            ft.TextButton("下载更新", on_click=on_download),
            ft.TextButton("忽略此版本", on_click=on_ignore),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END