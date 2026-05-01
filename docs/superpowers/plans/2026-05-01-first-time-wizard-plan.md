# 首次启动引导实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 小白用户首次启动时通过 3 步引导完成初始配置（API Key、自选股、通知渠道），跳过引导后顶部显示提示条。

**Architecture:** 在 TUIApp 启动时检测是否需要引导，如果需要则优先显示 WizardView，引导完成后进入 MarketsView。配置通过 Config.save_to_env() 持久化到 .env 文件。

**Tech Stack:** Textual (TUI), Python dataclass

---

## Task 1: 添加 Config.is_first_time_setup() 方法

**Files:**
- Modify: `src/config.py` (在 Config 类中添加方法)

- [ ] **Step 1: 在 Config 类中添加 is_first_time_setup 方法**

在 `src/config.py` 的 `Config` 类中找到 `refresh_from_updates` 方法之后，添加：

```python
def is_first_time_setup(self) -> bool:
    """
    检查是否需要显示首次启动引导

    满足以下任一条件返回 True：
    - .env 文件不存在
    - AI API Key 未配置
    - 自选股列表为空
    """
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        return True
    if not self.openai_api_key and not self.gemini_api_key:
        return True
    if not self.stock_list:
        return True
    return False
```

- [ ] **Step 2: 测试方法**

Run: `cd /Users/doug/code/python/open-daily-stock && python3 -c "from src.config import get_config; c = get_config(); print('is_first_time_setup:', c.is_first_time_setup())"`

Expected: 输出 True 或 False，取决于当前配置状态

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add Config.is_first_time_setup() method"
```

---

## Task 2: 创建 WizardView 组件

**Files:**
- Create: `tui/widgets/wizard.py`

- [ ] **Step 1: 创建 WizardView 组件**

创建 `tui/widgets/wizard.py`：

```python
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
```

- [ ] **Step 2: 测试导入**

Run: `cd /Users/doug/code/python/open-daily-stock && python3 -c "from tui.widgets.wizard import WizardView; print('WizardView OK')"`

Expected: WizardView OK（无输出错误）

- [ ] **Step 3: Commit**

```bash
git add tui/widgets/wizard.py
git commit -m "feat: add WizardView first-time setup component"
```

---

## Task 3: 集成 WizardView 到 TUIApp

**Files:**
- Modify: `tui/app.py` (添加 wizard 检测和显示逻辑)

- [ ] **Step 1: 修改 TUIApp.__init__ 检测引导条件**

在 `tui/app.py` 的 `__init__` 方法中，在 `self._task_store = TaskStore()` 后添加：

```python
# 检测是否需要首次启动引导
self._show_wizard = config.is_first_time_setup()
self._wizard_completed = False
```

- [ ] **Step 2: 修改 compose 方法有条件地挂载 Wizard**

找到 `compose` 方法，在开头添加 wizard 条件：

```python
def compose(self):
    if self._show_wizard and not self._wizard_completed:
        from tui.widgets.wizard import WizardView
        def on_wizard_complete():
            self._wizard_completed = True
            self._refresh_main_view()
        def on_wizard_skip():
            self._wizard_completed = True
            self.action_switch(0)  # 进入 Markets
        yield WizardView(on_complete_callback=on_wizard_complete, on_skip_callback=on_wizard_skip)
        return

    # 正常视图
    yield Header()
    yield Nav(active=0)
    yield Footer(last_update="---")
    yield MarketsView(self._dp)
    yield TasksView(self._task_store)
    yield AnalyzeView(self._on_analyze_callback)
    yield ConfigView()
    yield LogsView()
```

- [ ] **Step 3: 添加 _refresh_main_view 方法**

在 `TUIApp` 类中添加：

```python
def _refresh_main_view(self):
    """刷新主视图（在引导完成后调用）"""
    self._wizard_completed = True
    # 重新渲染主界面
    for widget in list(self.children):
        widget.remove()
    for w in self.compose():
        self.mount(w)
    # 开始轮询
    self._start_polling()
```

- [ ] **Step 4: 测试运行**

Run: `cd /Users/doug/code/python/open-daily-stock && python3 -c "from tui.app import TUIApp; print('TUIApp OK')"`

Expected: TUIApp OK（无输出错误）

- [ ] **Step 5: Commit**

```bash
git add tui/app.py
git commit -m "feat: integrate WizardView into TUIApp for first-time setup"
```

---

## Task 4: 添加跳过引导后的顶部提示条

**Files:**
- Modify: `tui/app.py` (在 MarketsView 顶部添加提示条)
- Modify: `tui/widgets/markets.py` (添加提示条显示逻辑)

- [ ] **Step 1: 修改 TUIApp 传递 wizard_completed 状态**

在 `TUIApp.__init__` 中添加：

```python
# 检测是否需要首次启动引导
self._show_wizard = config.is_first_time_setup()
self._wizard_completed = False
self._wizard_skipped = False  # 新增：用户是否跳过了引导
```

修改 `_refresh_main_view`:

```python
def _refresh_main_view(self):
    """刷新主视图（在引导完成后调用）"""
    self._wizard_completed = True
    for widget in list(self.children):
        widget.remove()
    for w in self.compose():
        self.mount(w)
    self._start_polling()
```

修改 `on_wizard_skip` 回调：

```python
def on_wizard_skip():
    self._wizard_completed = True
    self._wizard_skipped = True  # 标记用户跳过了引导
    self.action_switch(0)  # 进入 Markets
```

- [ ] **Step 2: 修改 MarketsView 添加提示条**

读取 `tui/widgets/markets.py`，在 `compose` 方法中，在开头添加提示条：

```python
def compose(self):
    # 跳过引导后的提示条
    app = self.app
    if getattr(app, '_wizard_skipped', False):
        yield Static("⚠️ 请先配置（按 4 进入 Config）", id="wizard-warning", styles={"background": "#ff6b6b", "color": "#ffffff"})
    yield Static("实时行情", id="markets-title")
    # ... 其余代码
```

- [ ] **Step 3: 测试**

Run: `cd /Users/doug/code/python/open-daily-stock && python3 -c "from tui.widgets.markets import MarketsView; print('MarketsView OK')"`

Expected: MarketsView OK

- [ ] **Step 4: Commit**

```bash
git add tui/app.py tui/widgets/markets.py
git commit -m "feat: add wizard skip warning banner in MarketsView"
```

---

## Task 5: 验证完整流程

- [ ] **Step 1: 删除 .env 文件模拟首次启动**

Run: `cd /Users/doug/code/python/open-daily-stock && rm -f .env && python3 main.py --tui 2>&1 | head -30`

Expected: 显示引导页面，而非直接进入 Markets

- [ ] **Step 2: 检查提示条显示**

当配置了 .env 但 API Key 为空时，检查是否显示提示条

- [ ] **Step 3: Commit all**

```bash
git status
git add -A
git commit -m "feat: complete first-time wizard feature"
```

---

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**