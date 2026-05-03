"""配置页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR
from src.config import get_config
from src.i18n import _, set_language


class ConfigPage(ft.Container):
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
        self._language_dropdown = None

        header = ft.Text(_("配置管理"), size=24, weight=ft.FontWeight.BOLD)

        # Load current config values
        config = get_config()

        # Pre-populate stock_list as comma-separated string
        stock_value = ','.join(config.stock_list) if config.stock_list else ''

        api_section = self._build_section(_("API 配置"), [
            (_("OpenAI API Key:"), config.openai_api_key or ""),
            (_("API 地址:"), config.openai_base_url or "https://api.minimax.chat/v1"),
            (_("模型名称:"), config.openai_model or "abab6-chat"),
        ])

        stock_section = self._build_section(_("自选股配置"), [
            (_("股票列表:"), stock_value),
        ])

        notify_section = self._build_section(_("通知配置"), [
            (_("企业微信:"), config.wechat_webhook_url or ""),
            (_("飞书:"), config.feishu_webhook_url or ""),
        ])

        # Language section
        self._language_dropdown = ft.Dropdown(
            label=_("语言"),
            value=config.language or "zh_CN",
            options=[
                ft.dropdown.Option("zh_CN", "简体中文"),
                ft.dropdown.Option("en_US", "English"),
            ],
            on_select=self._on_language_change,
        )

        language_section = ft.Container(
            content=ft.Column([
                ft.Text(_("语言设置"), size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                self._language_dropdown,
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        save_btn = ft.Button(
            _("保存配置"),
            icon=ft.Icons.SAVE,
            on_click=self._save_config,
            bgcolor=ACCENT_COLOR,
            color=ft.Colors.WHITE,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                api_section,
                ft.Container(height=20),
                stock_section,
                ft.Container(height=20),
                notify_section,
                ft.Container(height=20),
                language_section,
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
            if label == _("OpenAI API Key:"):
                self._api_key_field = text_field
            elif label == _("API 地址:"):
                self._base_url_field = text_field
            elif label == _("模型名称:"):
                self._model_field = text_field
            elif label == _("股票列表:"):
                self._stock_list_field = text_field
            elif label == _("企业微信:"):
                self._wechat_field = text_field
            elif label == _("飞书:"):
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
        if self._language_dropdown:
            updates['LANGUAGE'] = self._language_dropdown.value or 'zh_CN'

        # Save to .env file
        config = get_config()
        success = config.save_to_env(updates)

        if success:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("配置已保存")), open=True)
            )
        else:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("保存失败")), open=True)
            )

    def _on_language_change(self, e):
        """Handle language change"""
        if self._language_dropdown:
            set_language(self._language_dropdown.value)
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("语言已切换")), open=True)
            )