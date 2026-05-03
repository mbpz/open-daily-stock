"""Config module for editing settings."""
from textual.widgets import Static, Input, Button
from textual.events import Key
from src.config import get_config
from src.i18n import _


class ConfigView(Static):
    """配置管理页面 - 支持多配置项"""

    def __init__(self):
        super().__init__()
        self._config = get_config()
        self._selected_idx = 0
        self._fields = [
            {"key": "STOCK_LIST", "label": _("自选股列表"), "value": "", "hint": _("逗号分隔，如: 000001,600519")},
            {"key": "OPENAI_API_KEY", "label": _("OpenAI API Key"), "value": "", "hint": _("MiniMax/OpenAI 兼容 Key")},
            {"key": "OPENAI_BASE_URL", "label": _("API 地址"), "value": "", "hint": "MiniMax: https://api.minimax.chat/v1"},
            {"key": "OPENAI_MODEL", "label": _("模型名称"), "value": "", "hint": _("如: gpt-4o-mini 或 abab6-chat")},
            {"key": "GEMINI_API_KEY", "label": "Google Gemini API Key", "value": "", "hint": "Google Gemini API Key"},
            {"key": "WECHAT_WEBHOOK_URL", "label": _("企业微信 Webhook"), "value": "", "hint": _("企业微信群机器人 URL")},
            {"key": "FEISHU_WEBHOOK_URL", "label": _("飞书 Webhook"), "value": "", "hint": _("飞书群机器人 URL")},
        ]
        self._load_values()

    def _load_values(self):
        """从配置加载当前值"""
        self._fields[0]["value"] = ",".join(self._config.stock_list)
        self._fields[1]["value"] = self._config.openai_api_key or ""
        self._fields[2]["value"] = self._config.openai_base_url or ""
        self._fields[3]["value"] = self._config.openai_model or "gpt-4o-mini"
        self._fields[4]["value"] = self._config.gemini_api_key or ""
        self._fields[5]["value"] = self._config.wechat_webhook_url or ""
        self._fields[6]["value"] = self._config.feishu_webhook_url or ""

    def compose(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  配置管理  (↑↓ 选择，Enter 编辑，Esc 完成)"), id="nav-hint")
        yield Static("=" * 50, id="divider")

        for i, field in enumerate(self._fields):
            marker = "►" if i == self._selected_idx else " "
            yield Static(f"{marker} {field['label']}: {field['value'] or _('(未配置)')}", id=f"field-{i}")

        yield Static("", id="hint-line")
        yield Static("", id="input-area")
        yield Static("", id="save-status")
        yield Static(_("  ↑↓ 选择  Enter 编辑  Esc 保存并退出"), id="footer-hint")

    def _refresh_display(self):
        """刷新显示"""
        for i, field in enumerate(self._fields):
            marker = "►" if i == self._selected_idx else " "
            display_value = field['value'] or _('(未配置)')
            el = self.query_one(f"#field-{i}", Static)
            el.update(f"{marker} {field['label']}: {display_value}")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
        # 确保 ConfigView 获得焦点以接收键盘事件
        self.focus()

    def on_key(self, event: Key):
        if event.key == "escape":
            self._save_all()
            return
        elif event.key == "up":
            self._selected_idx = max(0, self._selected_idx - 1)
            self._refresh_display()
        elif event.key == "down":
            self._selected_idx = min(len(self._fields) - 1, self._selected_idx + 1)
            self._refresh_display()
        elif event.key == "enter":
            self._edit_current_field()

    def _edit_current_field(self):
        """编辑当前选中字段"""
        field = self._fields[self._selected_idx]
        self.query_one("#input-area", Static).update(f"[编辑 {field['label']}] ")
        input_widget = Input(value=field['value'], id="config-input")
        input_widget.focus()

        # 替换 input-area
        old = self.query_one("#input-area")
        old.remove_children()
        old.remove()
        self.mount(input_widget)

        def on_submit(event):
            field['value'] = event.value
            input_widget.remove()
            self._save_current_field()
            self._refresh_display()

        input_widget.on_submit = on_submit

    def _save_current_field(self):
        """保存当前字段到配置"""
        field = self._fields[self._selected_idx]
        if field['key'] == 'STOCK_LIST':
            self._config.stock_list = [s.strip() for s in field['value'].split(',') if s.strip()]
        elif field['key'] == 'OPENAI_API_KEY':
            self._config.openai_api_key = field['value'] or None
        elif field['key'] == 'OPENAI_BASE_URL':
            self._config.openai_base_url = field['value'] or None
        elif field['key'] == 'OPENAI_MODEL':
            self._config.openai_model = field['value'] or 'gpt-4o-mini'
        elif field['key'] == 'GEMINI_API_KEY':
            self._config.gemini_api_key = field['value'] or None
        elif field['key'] == 'WECHAT_WEBHOOK_URL':
            self._config.wechat_webhook_url = field['value'] or None
        elif field['key'] == 'FEISHU_WEBHOOK_URL':
            self._config.feishu_webhook_url = field['value'] or None

    def _save_all(self):
        """保存所有配置到 .env"""
        updates = {}
        for field in self._fields:
            if field['value']:
                updates[field['key']] = field['value']

        if updates:
            success = self._config.save_to_env(updates)
            status = _("✓ 配置已保存到 .env") if success else _("✗ 保存失败")
        else:
            status = _("✓ 无需保存")

        self.query_one("#save-status", Static).update(f"  {status}")