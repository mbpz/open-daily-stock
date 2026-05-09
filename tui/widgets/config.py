"""Config module for editing settings."""
import json
from pathlib import Path
from textual.widgets import Static, Input, Button
from textual.events import Key
from src.config import get_config
from src.i18n import _

_ALERTS_FILE = Path(__file__).parent.parent.parent / "config.json"


class ConfigView(Static):
    """配置管理页面 - 支持多配置项 + 告警配置"""

    def __init__(self):
        super().__init__()
        self._config = get_config()
        self._selected_idx = 0
        self._mode = "config"  # "config" or "alerts"
        self._alerts_list = []
        self._alert_selected_idx = 0
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
        self._load_alerts()

    def _load_values(self):
        """从配置加载当前值"""
        self._fields[0]["value"] = ",".join(self._config.stock_list)
        self._fields[1]["value"] = self._config.openai_api_key or ""
        self._fields[2]["value"] = self._config.openai_base_url or ""
        self._fields[3]["value"] = self._config.openai_model or "gpt-4o-mini"
        self._fields[4]["value"] = self._config.gemini_api_key or ""
        self._fields[5]["value"] = self._config.wechat_webhook_url or ""
        self._fields[6]["value"] = self._config.feishu_webhook_url or ""

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

    def compose(self):
        if self._mode == "config":
            yield from self._compose_config()
        else:
            yield from self._compose_alerts()

    def _compose_config(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  配置管理  (↑↓ 选择，Enter 编辑，Tab 切换到告警)"), id="nav-hint")
        yield Static("=" * 50, id="divider")

        for i, field in enumerate(self._fields):
            marker = "►" if i == self._selected_idx else " "
            yield Static(f"{marker} {field['label']}: {field['value'] or _('(未配置)')}", id=f"field-{i}")

        yield Static("", id="hint-line")
        yield Static("", id="input-area")
        yield Static("", id="save-status")
        yield Static(_("  ↑↓ 选择  Enter 编辑  Tab 告警  Esc 保存退出"), id="footer-hint")

    def _compose_alerts(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  告警配置  (↑↓ 选择，d 删除，e 启用/禁用，a 添加)"), id="nav-hint")
        yield Static("=" * 50, id="divider")

        if not self._alerts_list:
            yield Static(_("  (暂无告警配置，按 a 添加)"), id="no-alerts")
        else:
            for i, alert in enumerate(self._alerts_list):
                marker = "►" if i == self._alert_selected_idx else " "
                enabled = "●" if alert.get('enabled', True) else "○"
                stock = alert.get('stock', '')
                condition = alert.get('condition', 'price_above').replace('_', ' ').title()
                value = alert.get('value', '')
                channel = alert.get('channel', 'wechat')
                yield Static(f"{marker}{enabled} {stock} {condition} {value} → {channel}", id=f"alert-{i}")

        yield Static("", id="hint-line")
        yield Static("", id="input-area")
        yield Static("", id="save-status")
        yield Static(_("  ↑↓ 选择  a 添加  d 删除  e 切换  Tab 配置  Esc 退出"), id="footer-hint")

    def _refresh_display(self):
        for i, field in enumerate(self._fields):
            marker = "►" if i == self._selected_idx else " "
            display_value = field['value'] or _('(未配置)')
            el = self.query_one(f"#field-{i}", Static)
            el.update(f"{marker} {field['label']}: {display_value}")

    def _refresh_alerts_display(self):
        if not self._alerts_list:
            try:
                el = self.query_one("#no-alerts", Static)
                el.update(_("  (暂无告警配置，按 a 添加)"))
            except Exception:
                pass
        else:
            for i, alert in enumerate(self._alerts_list):
                marker = "►" if i == self._alert_selected_idx else " "
                enabled = "●" if alert.get('enabled', True) else "○"
                stock = alert.get('stock', '')
                condition = alert.get('condition', 'price_above').replace('_', ' ').title()
                value = alert.get('value', '')
                channel = alert.get('channel', 'wechat')
                try:
                    el = self.query_one(f"#alert-{i}", Static)
                    el.update(f"{marker}{enabled} {stock} {condition} {value} → {channel}")
                except Exception:
                    pass

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
        self.focus()

    def on_key(self, event: Key):
        if self._mode == "config":
            self._handle_config_key(event)
        else:
            self._handle_alerts_key(event)

    def _handle_config_key(self, event: Key):
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
        elif event.key == "tab":
            self._mode = "alerts"
            self._selected_idx = 0
            self._refresh_alerts_view()

    def _handle_alerts_key(self, event: Key):
        if event.key == "escape":
            return
        elif event.key == "up":
            self._alert_selected_idx = max(0, self._alert_selected_idx - 1)
            self._refresh_alerts_display()
        elif event.key == "down":
            if self._alerts_list:
                self._alert_selected_idx = min(len(self._alerts_list) - 1, self._alert_selected_idx + 1)
            self._refresh_alerts_display()
        elif event.key == "a":
            self._add_alert_interactive()
        elif event.key == "d":
            self._delete_current_alert()
        elif event.key == "e":
            self._toggle_current_alert()
        elif event.key == "tab":
            self._mode = "config"
            self.refresh()

    def _refresh_alerts_view(self):
        """Refresh to alerts view"""
        self.query("#header").clear()
        self.query("#nav-hint").clear()
        self.query("#divider").clear()
        # Remove old elements
        for i in range(len(self._fields)):
            try:
                self.query_one(f"#field-{i}", Static).remove()
            except Exception:
                pass
        try:
            self.query_one("#hint-line", Static).remove()
            self.query_one("#input-area", Static).remove()
            self.query_one("#save-status", Static).remove()
            self.query_one("#footer-hint", Static).remove()
        except Exception:
            pass
        # Mount new alerts elements
        for el in self._compose_alerts():
            self.mount(el)
        self.refresh()

    def _edit_current_field(self):
        """编辑当前选中字段"""
        field = self._fields[self._selected_idx]
        self.query_one("#input-area", Static).update(f"[编辑 {field['label']}] ")
        input_widget = Input(value=field['value'], id="config-input")
        input_widget.focus()

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

    def _add_alert_interactive(self):
        """Add alert in interactive mode"""
        self.query_one("#input-area", Static).update(_("[添加告警] 输入格式: 股票代码,条件,阈值,渠道 "))
        input_widget = Input(value="", id="config-input", placeholder="600519,price_above,200,wechat")
        input_widget.focus()

        try:
            old = self.query_one("#input-area")
            old.remove_children()
            old.remove()
        except Exception:
            pass
        self.mount(input_widget)

        def on_submit(event):
            input_widget.remove()
            parts = event.value.strip().split(',')
            if len(parts) >= 4:
                alert = {
                    'stock': parts[0].strip(),
                    'condition': parts[1].strip(),
                    'value': parts[2].strip(),
                    'channel': parts[3].strip(),
                    'enabled': True,
                }
                self._alerts_list.append(alert)
                self._save_alerts()
            self._refresh_alerts_view()

        input_widget.on_submit = on_submit

    def _delete_current_alert(self):
        """Delete current alert"""
        if 0 <= self._alert_selected_idx < len(self._alerts_list):
            self._alerts_list.pop(self._alert_selected_idx)
            self._save_alerts()
            self._alert_selected_idx = min(self._alert_selected_idx, max(0, len(self._alerts_list) - 1))
            self._refresh_alerts_view()

    def _toggle_current_alert(self):
        """Toggle current alert enabled state"""
        if 0 <= self._alert_selected_idx < len(self._alerts_list):
            self._alerts_list[self._alert_selected_idx]['enabled'] = not self._alerts_list[self._alert_selected_idx].get('enabled', True)
            self._save_alerts()
            self._refresh_alerts_display()