"""配置页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR

class ConfigPage(ft.UserControl):
    """配置管理页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        header = ft.Text("配置管理", size=24, weight=ft.FontWeight.BOLD)

        api_section = self._build_section("API 配置", [
            ("OpenAI API Key:", "输入你的 API Key"),
            ("API 地址:", "https://api.minimax.chat/v1"),
            ("模型名称:", "abab6-chat"),
        ])

        stock_section = self._build_section("自选股配置", [
            ("股票列表:", "000001,600519,000002"),
        ])

        notify_section = self._build_section("通知配置", [
            ("企业微信:", "Webhook URL（可选）"),
            ("飞书:", "Webhook URL（可选）"),
        ])

        save_btn = ft.ElevatedButton(
            "保存配置",
            icon=ft.icons.SAVE,
            on_click=self._save_config,
            bgcolor=ACCENT_COLOR,
            color=ft.WHITE,
        )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                api_section,
                ft.Container(height=20),
                stock_section,
                ft.Container(height=20),
                notify_section,
                ft.Container(height=20),
                save_btn,
            ]),
            padding=10,
        )

    def _build_section(self, title: str, fields: list) -> ft.Container:
        """构建配置区块"""
        field_controls = []
        for label, hint in fields:
            field_controls.append(
                ft.Row([
                    ft.Text(label, width=120),
                    ft.TextField(
                        hint_text=hint,
                        expand=True,
                    ),
                ])
            )

        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                *field_controls,
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
        )

    def _save_config(self, e):
        """保存配置"""
        # TODO: 保存到 Config
        self.app.page.show_snack_bar(
            ft.SnackBar(content=ft.Text("配置已保存"), open=True)
        )