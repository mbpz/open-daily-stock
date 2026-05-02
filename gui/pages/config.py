"""配置页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR
from src.config import get_config


class ConfigPage(ft.UserControl):
    """配置管理页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        # Field references for accessing values
        self._api_key_field = None
        self._base_url_field = None
        self._model_field = None
        self._stock_list_field = None
        self._wechat_field = None
        self._feishu_field = None

    def build(self):
        header = ft.Text("配置管理", size=24, weight=ft.FontWeight.BOLD)

        # Load current config values
        config = get_config()

        # Pre-populate stock_list as comma-separated string
        stock_value = ','.join(config.stock_list) if config.stock_list else ''

        api_section = self._build_section("API 配置", [
            ("OpenAI API Key:", config.openai_api_key or ""),
            ("API 地址:", config.openai_base_url or "https://api.minimax.chat/v1"),
            ("模型名称:", config.openai_model or "abab6-chat"),
        ])

        stock_section = self._build_section("自选股配置", [
            ("股票列表:", stock_value),
        ])

        notify_section = self._build_section("通知配置", [
            ("企业微信:", config.wechat_webhook_url or ""),
            ("飞书:", config.feishu_webhook_url or ""),
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
        """构建配置区块

        Args:
            title: Section title
            fields: List of (label, value) tuples for each field
        """
        field_controls = []
        for label, value in fields:
            text_field = ft.TextField(
                hint_text=label,
                value=value,
                expand=True,
            )
            field_controls.append(
                ft.Row([
                    ft.Text(label, width=120),
                    text_field,
                ])
            )
            # Store references to specific fields
            if label == "OpenAI API Key:":
                self._api_key_field = text_field
            elif label == "API 地址:":
                self._base_url_field = text_field
            elif label == "模型名称:":
                self._model_field = text_field
            elif label == "股票列表:":
                self._stock_list_field = text_field
            elif label == "企业微信:":
                self._wechat_field = text_field
            elif label == "飞书:":
                self._feishu_field = text_field

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
        # Build updates dict from field values
        updates = {}

        if self._api_key_field:
            updates['OPENAI_API_KEY'] = self._api_key_field.value or ''
        if self._base_url_field:
            updates['OPENAI_BASE_URL'] = self._base_url_field.value or ''
        if self._model_field:
            updates['OPENAI_MODEL'] = self._model_field.value or ''
        if self._stock_list_field:
            updates['STOCK_LIST'] = self._stock_list_field.value or ''
        if self._wechat_field:
            updates['WECHAT_WEBHOOK_URL'] = self._wechat_field.value or ''
        if self._feishu_field:
            updates['FEISHU_WEBHOOK_URL'] = self._feishu_field.value or ''

        # Save to .env file
        config = get_config()
        success = config.save_to_env(updates)

        if success:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("配置已保存"), open=True)
            )
        else:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text("保存失败"), open=True)
            )