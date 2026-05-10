"""配置页面"""
import flet as ft
import json
from pathlib import Path
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR, SUCCESS_COLOR, ERROR_COLOR
from src.config import get_config
from src.i18n import _, set_language

# Alerts storage path
_ALERTS_FILE = Path(__file__).parent.parent.parent / "config.json"


class ConfigPage(ft.Container):
    """配置管理页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._api_key_field = None
        self._base_url_field = None
        self._model_field = None
        self._stock_list_field = None
        self._wechat_field = None
        self._feishu_field = None
        self._language_dropdown = None
        self._alert_stock_field = None
        self._alert_condition_field = None
        self._alert_channel_field = None
        self._alerts_list = []
        self._selected_alert_idx = None

        self._load_alerts()

        header = ft.Text(_("配置管理"), size=24, weight=ft.FontWeight.BOLD)

        config = get_config()
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

        # Alerts section
        alerts_section = self._build_alerts_section()

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
                alerts_section,
                ft.Container(height=20),
                save_btn,
                self._build_exit_demo_btn() if config.is_demo_mode() else ft.Container(),
            ], scroll=ft.ScrollMode.AUTO),
            padding=10,
        )

    def _load_alerts(self):
        """Load alerts from config.json"""
        try:
            if _ALERTS_FILE.exists():
                with open(_ALERTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._alerts_list = data.get('alerts', [])
            else:
                self._alerts_list = []
        except Exception:
            self._alerts_list = []

    def _save_alerts(self):
        """Save alerts to config.json"""
        try:
            data = {}
            if _ALERTS_FILE.exists():
                with open(_ALERTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data['alerts'] = self._alerts_list
            with open(_ALERTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存告警配置失败: {e}")

    def _build_alerts_section(self) -> ft.Container:
        """Build alerts management section"""
        # Header
        title = ft.Text(_("告警配置"), size=16, weight=ft.FontWeight.BOLD)

        # Alert list display
        self._alerts_list_view = ft.ListView(expand=True, spacing=10)

        # Add alert form
        self._alert_stock_field = ft.TextField(
            hint_text=_("股票代码"),
            width=120,
        )
        self._alert_condition_field = ft.Dropdown(
            hint_text=_("条件"),
            width=180,
            options=[
                ft.dropdown.Option("price_above", _("价格高于")),
                ft.dropdown.Option("price_below", _("价格低于")),
            ],
        )
        self._alert_value_field = ft.TextField(
            hint_text=_("阈值"),
            width=100,
        )
        self._alert_channel_field = ft.Dropdown(
            hint_text=_("通知渠道"),
            width=120,
            options=[
                ft.dropdown.Option("wechat", _("企业微信")),
                ft.dropdown.Option("feishu", _("飞书")),
                ft.dropdown.Option("telegram", "Telegram"),
                ft.dropdown.Option("email", _("邮件")),
            ],
        )

        add_btn = ft.Button(
            _("添加告警"),
            icon=ft.Icons.ADD,
            on_click=self._add_alert,
            bgcolor=SUCCESS_COLOR,
            color=ft.Colors.WHITE,
        )

        form_row = ft.Row([
            self._alert_stock_field,
            self._alert_condition_field,
            self._alert_value_field,
            self._alert_channel_field,
            add_btn,
        ])

        content = ft.Column([
            title,
            ft.Container(height=10),
            form_row,
            ft.Container(height=10),
            ft.Container(
                content=self._alerts_list_view,
                height=150,
                border=ft.border.all(1, CARD_BORDER),
                border_radius=5,
                padding=5,
            ),
        ])

        container = ft.Container(
            content=content,
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        self._refresh_alerts_list()
        return container

    def _refresh_alerts_list(self):
        """Refresh the alerts list display"""
        self._alerts_list_view.controls.clear()
        for i, alert in enumerate(self._alerts_list):
            enabled = alert.get('enabled', True)
            stock = alert.get('stock', '')
            condition = alert.get('condition', '')
            value = alert.get('value', '')
            channel = alert.get('channel', 'wechat')

            condition_text = condition.replace('_', ' ').title()

            row = ft.Row([
                ft.IconButton(
                    icon=ft.Icons.TOGGLE_ON if enabled else ft.Icons.TOGGLE_OFF,
                    icon_color=SUCCESS_COLOR if enabled else ERROR_COLOR,
                    on_click=lambda e, idx=i: self._toggle_alert(idx),
                    icon_size=20,
                ),
                ft.Text(f"{stock} {condition_text} {value}", expand=True),
                ft.Text(f"→ {channel}", color=ft.Colors.GREY),
                ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=ERROR_COLOR,
                    on_click=lambda e, idx=i: self._delete_alert(idx),
                    icon_size=20,
                ),
            ])
            self._alerts_list_view.controls.append(row)
        try:
            self._alerts_list_view.update()
        except Exception:
            pass

    def _toggle_alert(self, idx: int):
        """Toggle alert enabled state"""
        if 0 <= idx < len(self._alerts_list):
            self._alerts_list[idx]['enabled'] = not self._alerts_list[idx].get('enabled', True)
            self._save_alerts()
            self._refresh_alerts_list()

    def _delete_alert(self, idx: int):
        """Delete an alert"""
        if 0 <= idx < len(self._alerts_list):
            self._alerts_list.pop(idx)
            self._save_alerts()
            self._refresh_alerts_list()

    def _add_alert(self, e):
        """Add a new alert"""
        stock = self._alert_stock_field.value.strip()
        condition = self._alert_condition_field.value
        value = self._alert_value_field.value.strip()
        channel = self._alert_channel_field.value or 'wechat'

        if not stock or not condition or not value:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("请填写完整的告警信息")), open=True)
            )
            return

        try:
            float(value)
        except ValueError:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("阈值必须是数字")), open=True)
            )
            return

        alert = {
            'stock': stock,
            'condition': condition,
            'value': value,
            'channel': channel,
            'enabled': True,
        }
        self._alerts_list.append(alert)
        self._save_alerts()
        self._refresh_alerts_list()

        # Clear form
        self._alert_stock_field.value = ''
        self._alert_value_field.value = ''
        self._alert_stock_field.update()
        self._alert_value_field.update()

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

    def _build_exit_demo_btn(self) -> ft.Container:
        """Build exit demo mode button (P5-4)."""
        return ft.Container(
            content=ft.Column([
                ft.Text(_("演示模式"), size=16, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ORANGE),
                ft.Text(_("当前处于演示模式，AI 分析使用预计算结果。"
                          "配置 API Key 后即可解锁实时分析。"),
                        size=13, color=ft.Colors.GREY),
                ft.Container(height=10),
                ft.Button(
                    _("退出演示模式"),
                    icon=ft.Icons.EXIT_TO_APP,
                    on_click=self._exit_demo_mode,
                    bgcolor=ACCENT_COLOR,
                    color=ft.Colors.WHITE,
                ),
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
        )

    def _exit_demo_mode(self, e):
        """Handle exit demo mode button click."""
        from src.demo_data import exit_demo_mode

        config = get_config()
        exit_demo_mode(config)
        config.__class__.reset_instance()

        # Show success message and suggest reload
        self.app.page.show_snack_bar(
            ft.SnackBar(content=ft.Text(_("已退出演示模式，请重新启动应用以完成设置")), open=True)
        )

    def _on_language_change(self, e):
        """Handle language change"""
        if self._language_dropdown:
            set_language(self._language_dropdown.value)
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("语言已切换")), open=True)
            )