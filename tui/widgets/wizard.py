"""首次启动引导组件"""
from textual.widgets import Static, Input
from textual.events import Key
from src.config import get_config


class WizardView(Static):
    """首次启动引导页面 - 3 步分步表单"""

    WIZARD_STEPS = [
        {
            "title": "配置 API Key",
            "fields": [
                {"key": "OPENAI_API_KEY", "label": "OpenAI/MiniMax API Key", "hint": "输入你的 API Key（如 MiniMax eyJ...）", "required": True},
                {"key": "OPENAI_BASE_URL", "label": "API 地址", "hint": "MiniMax: https://api.minimax.chat/v1", "required": False},
                {"key": "OPENAI_MODEL", "label": "模型名称", "hint": "如: abab6-chat 或 gpt-4o-mini", "required": False},
            ]
        },
        {
            "title": "配置自选股",
            "fields": [
                {"key": "STOCK_LIST", "label": "自选股列表", "hint": "逗号分隔，如: 000001,600519,000002", "required": True},
            ]
        },
        {
            "title": "配置通知渠道（可选）",
            "fields": [
                {"key": "WECHAT_WEBHOOK_URL", "label": "企业微信 Webhook", "hint": "企业微信群机器人 URL（可选）", "required": False},
                {"key": "FEISHU_WEBHOOK_URL", "label": "飞书 Webhook", "hint": "飞书群机器人 URL（可选）", "required": False},
            ],
            "skippable": True,
        },
    ]

    def __init__(self, on_complete_callback=None, on_skip_callback=None):
        super().__init__()
        self._config = get_config()
        self._current_step = 0
        self._field_values = {}
        self._selected_field_idx = 0
        self._on_complete = on_complete_callback
        self._on_skip = on_skip_callback

    def compose(self):
        step = self.WIZARD_STEPS[self._current_step]
        yield Static("=" * 50, id="wizard-header")
        yield Static(f"  欢迎使用 open-daily-stock", id="wizard-title")
        yield Static(f"  首次启动需要完成以下配置", id="wizard-subtitle")
        yield Static("=" * 50, id="wizard-divider")
        yield Static("", id="wizard-spacer")

        # 步骤标题
        yield Static(f"步骤 {self._current_step + 1}/{len(self.WIZARD_STEPS)}: {step['title']}", id="step-title")

        # 字段列表
        for i, field in enumerate(step["fields"]):
            marker = "►" if i == self._selected_field_idx else " "
            current_value = self._field_values.get(field["key"], "")
            display_value = current_value if current_value else "(未配置)"
            yield Static(f"{marker} {field['label']}: {display_value}", id=f"wizard-field-{i}")

        # 提示
        yield Static("", id="wizard-hint-area")
        yield Static("", id="wizard-input-area")

        # 底部提示
        skip_hint = " | Esc 跳过" if step.get("skippable") else ""
        yield Static(f"  ↑↓ 选择  Enter 编辑  Enter 继续{skip_hint}", id="wizard-footer")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 2)
        # 确保 WizardView 获得焦点以接收键盘事件
        self.focus()

    def on_key(self, event: Key):
        step = self.WIZARD_STEPS[self._current_step]

        if event.key == "escape":
            if step.get("skippable"):
                self._on_skip()
            return

        elif event.key == "up":
            self._selected_field_idx = max(0, self._selected_field_idx - 1)
            self._refresh_display()

        elif event.key == "down":
            self._selected_field_idx = min(len(step["fields"]) - 1, self._selected_field_idx + 1)
            self._refresh_display()

        elif event.key == "enter":
            # 检查是否有输入框活跃
            if self.query("Input"):
                return

            field = step["fields"][self._selected_field_idx]
            self._edit_field(field)

    def _refresh_display(self):
        """刷新字段显示"""
        step = self.WIZARD_STEPS[self._current_step]
        for i, field in enumerate(step["fields"]):
            marker = "►" if i == self._selected_field_idx else " "
            current_value = self._field_values.get(field["key"], "")
            display_value = current_value if current_value else "(未配置)"
            el = self.query_one(f"#wizard-field-{i}", Static)
            el.update(f"{marker} {field['label']}: {display_value}")

        skip_hint = " | Esc 跳过" if step.get("skippable") else ""
        self.query_one("#wizard-footer", Static).update(
            f"  ↑↓ 选择  Enter 编辑  Enter 继续{skip_hint}"
        )

    def _edit_field(self, field: dict):
        """编辑当前字段"""
        current_value = self._field_values.get(field["key"], "")
        self.query_one("#wizard-hint-area", Static).update(f"[编辑 {field['label']}] ")
        input_widget = Input(value=current_value, id="wizard-input")
        input_widget.focus()

        old = self.query_one("#wizard-input-area")
        old.remove_children()
        old.remove()
        self.mount(input_widget)

        def on_submit(event):
            self._field_values[field["key"]] = event.value
            input_widget.remove()
            self._refresh_display()
            # 重新聚焦到 wizard 以接收键盘事件
            self.focus()

        input_widget.on_submit = on_submit

    def _go_to_next_step(self):
        """进入下一步"""
        step = self.WIZARD_STEPS[self._current_step]

        # 保存当前步骤的值到配置
        for field in step["fields"]:
            key = field["key"]
            value = self._field_values.get(key, "")
            if key == "STOCK_LIST":
                self._config.stock_list = [s.strip() for s in value.split(",") if s.strip()]
            elif key == "OPENAI_API_KEY":
                self._config.openai_api_key = value or None
            elif key == "OPENAI_BASE_URL":
                self._config.openai_base_url = value or None
            elif key == "OPENAI_MODEL":
                self._config.openai_model = value or "gpt-4o-mini"
            elif key == "WECHAT_WEBHOOK_URL":
                self._config.wechat_webhook_url = value or None
            elif key == "FEISHU_WEBHOOK_URL":
                self._config.feishu_webhook_url = value or None

        # 如果是最后一步，完成引导
        if self._current_step >= len(self.WIZARD_STEPS) - 1:
            self._complete_wizard()
            return

        # 进入下一步
        self._current_step += 1
        self._selected_field_idx = 0
        self._clear_and_recompose()

    def _complete_wizard(self):
        """完成引导，保存配置并进入主界面"""
        # 保存到 .env
        updates = {}
        for key, value in self._field_values.items():
            if value:
                updates[key] = value
        self._config.save_to_env(updates)

        # 通知完成
        if self._on_complete:
            self._on_complete()

    def _skip_wizard(self):
        """跳过引导"""
        if self._on_skip:
            self._on_skip()

    def _clear_and_recompose(self):
        """清除并重新组合"""
        for widget in list(self.children):
            widget.remove()
        for w in self.compose():
            self.mount(w)