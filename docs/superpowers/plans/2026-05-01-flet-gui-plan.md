# Flet GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 Flet 桌面客户端，包含 5 个页面（行情、分析、任务、配置、日志）

**Architecture:** gui/ 目录新增 Flet 页面，共享 src/ 核心业务。左侧导航切换页面，右侧内容区显示页面内容。

**Tech Stack:** Flet, PyInstaller

---

## Task 1: 创建 gui/ 目录结构

**Files:**
- Create: `gui/__init__.py`
- Create: `gui/main.py`
- Create: `gui/app.py`
- Create: `gui/theme.py`
- Create: `gui/pages/__init__.py`
- Create: `gui/components/__init__.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p gui/pages gui/components
touch gui/__init__.py gui/pages/__init__.py gui/components/__init__.py
```

- [ ] **Step 2: 创建 gui/theme.py**

```python
"""Flet GUI 主题配置"""
from flet import Theme, Colors

# 主色调
PRIMARY_COLOR = "#1a1a2e"      # 深蓝黑背景
SECONDARY_COLOR = "#16213e"    # 次级背景
ACCENT_COLOR = "#0f3460"       # 强调色
HIGHLIGHT_COLOR = "#e94560"    # 高亮红

# 文字颜色
TEXT_PRIMARY = "#e8e8e8"        # 主文字
TEXT_SECONDARY = "#a0a0a0"    # 次级文字
TEXT_MUTED = "#666666"         # 暗淡文字

# 状态颜色
SUCCESS_COLOR = "#4caf50"       # 涨/成功
ERROR_COLOR = "#f44336"        # 跌/错误
WARNING_COLOR = "#ff9800"      # 警告

# 卡片样式
CARD_BG = "#16213e"
CARD_BORDER = "#0f3460"

def get_dark_theme() -> Theme:
    """返回深色主题配置"""
    return Theme(
        color_scheme_seed=PRIMARY_COLOR,
        brightness="dark",
    )
```

- [ ] **Step 3: 创建 gui/main.py**

```python
"""Flet GUI 入口"""
import flet as ft

def main(page: ft.Page):
    """GUI 主入口"""
    from gui.app import StockApp
    app = StockApp(page)
    app.run()

if __name__ == "__main__":
    ft.app(target=main)
```

- [ ] **Step 4: 创建 gui/app.py**

```python
"""Flet App 主类"""
import flet as ft
from gui.theme import (
    PRIMARY_COLOR, TEXT_PRIMARY, TEXT_SECONDARY,
    CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR
)

class StockApp:
    """股票分析桌面应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "A股分析助手"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.padding = 0
        self._current_page = "markets"
        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        # 左侧导航
        self.nav = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=150,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.icons.SHOW_CHART,
                    selected_icon=ft.icons.SHOW_CHART,
                    label="行情"
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.ANALYTICS,
                    selected_icon=ft.icons.ANALYTICS,
                    label="分析"
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.HISTORY,
                    selected_icon=ft.icons.HISTORY,
                    label="任务"
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.SETTINGS,
                    selected_icon=ft.icons.SETTINGS,
                    label="配置"
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.DESCRIPTION,
                    selected_icon=ft.icons.DESCRIPTION,
                    label="日志"
                ),
            ],
            on_change=self._on_nav_change,
        )

        # 内容区
        self.content_area = ft.Container(
            content=ft.Text("加载中...", size=20),
            expand=True,
            padding=20,
        )

        # 顶部状态栏
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Text("最后更新: ---", size=12, color="#a0a0a0"),
                ft.Container(expand=True),
                ft.Text("A股分析助手 v0.0.11", size=12, color="#666666"),
            ]),
            padding=10,
            bgcolor="#0f3460",
        )

        # 页面布局
        self.page.add(
            ft.Column([
                self.status_bar,
                ft.Expanded(
                    ft.Row([
                        self.nav,
                        ft.VerticalDivider(width=1, color="#0f3460"),
                        self.content_area,
                    ], expand=True)
                ),
            ], expand=True)
        )

        # 加载默认页面
        self._load_page("markets")

    def _on_nav_change(self, e):
        """导航切换"""
        pages = ["markets", "analyze", "tasks", "config", "logs"]
        self._current_page = pages[e.control.selected_index]
        self._load_page(self._current_page)

    def _load_page(self, page_name: str):
        """加载页面"""
        if page_name == "markets":
            from gui.pages.markets import MarketsPage
            self.content_area.content = MarketsPage(self)
        elif page_name == "analyze":
            from gui.pages.analyze import AnalyzePage
            self.content_area.content = AnalyzePage(self)
        elif page_name == "tasks":
            from gui.pages.tasks import TasksPage
            self.content_area.content = TasksPage(self)
        elif page_name == "config":
            from gui.pages.config import ConfigPage
            self.content_area.content = ConfigPage(self)
        elif page_name == "logs":
            from gui.pages.logs import LogsPage
            self.content_area.content = LogsPage(self)
        self.page.update()

    def update_status(self, message: str):
        """更新状态栏"""
        self.status_bar.content.controls[0] = ft.Text(
            f"最后更新: {message}", size=12, color="#a0a0a0"
        )
        self.page.update()
```

- [ ] **Step 5: Commit**

```bash
git add gui/ && git commit -m "feat: add Flet GUI basic structure"
```

---

## Task 2: 创建 MarketsPage（行情页）

**Files:**
- Create: `gui/pages/markets.py`

- [ ] **Step 1: 创建 gui/pages/markets.py`

```python
"""行情页面"""
import flet as ft
from datetime import datetime
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER

class MarketsPage(ft.UserControl):
    """行情展示页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        # 标题栏
        header = ft.Row([
            ft.Text("自选股行情", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.icons.REFRESH,
                on_click=self._refresh,
                tooltip="刷新",
            ),
        ])

        # 行情表格
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("代码", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("名称", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("最新价", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("涨跌幅", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("成交量", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )

        # 加载数据
        self._load_data()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                ft.Container(
                    content=self.table,
                    padding=10,
                    bgcolor=CARD_BG,
                    border_radius=10,
                ),
            ]),
            padding=10,
        )

    def _load_data(self):
        """加载行情数据"""
        # TODO: 接入 DataProviderWrapper
        # 暂时显示示例数据
        example_data = [
            ("600519", "贵州茅台", "1690.00", "+0.60%", "1000万"),
            ("000001", "平安银行", "12.50", "+0.85%", "1500万"),
        ]
        for row in example_data:
            code, name, price, change, volume = row
            change_color = SUCCESS_COLOR if "+" in change else ERROR_COLOR
            self.table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(code)),
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(price)),
                    ft.DataCell(ft.Text(change, color=change_color)),
                    ft.DataCell(ft.Text(volume)),
                ])
            )

    def _refresh(self, e):
        """刷新数据"""
        self.table.rows.clear()
        self._load_data()
        self.update()
        self.app.update_status(datetime.now().strftime("%H:%M:%S"))
```

- [ ] **Step 2: Commit**

```bash
git add gui/pages/markets.py && git commit -m "feat: add MarketsPage (行情页)"
```

---

## Task 3: 创建 AnalyzePage（分析页）

**Files:**
- Create: `gui/pages/analyze.py`

- [ ] **Step 1: 创建 gui/pages/analyze.py**

```python
"""分析页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ACCENT_COLOR

class AnalyzePage(ft.UserControl):
    """股票分析页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._stock_input = None
        self._result_area = None
        self._analyzing = False

    def build(self):
        # 标题
        header = ft.Text("股票分析", size=24, weight=ft.FontWeight.BOLD)

        # 股票输入区
        input_row = ft.Row([
            ft.Text("股票代码:", width=100),
            self._stock_input := ft.TextField(
                hint_text="如: 600519",
                width=200,
            ),
            ft.Container(width=20),
            ft.ElevatedButton(
                "开始分析",
                icon=ft.icons.PLAY_ARROW,
                on_click=self._start_analysis,
                bgcolor=ACCENT_COLOR,
                color=ft.WHITE,
            ),
        ])

        # 结果显示区
        self._result_area = ft.Container(
            content=ft.Text("分析结果将显示在这里", color="#a0a0a0"),
            padding=20,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=True,
        )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                input_row,
                ft.Container(height=20),
                self._result_area,
            ]),
            padding=10,
        )

    def _start_analysis(self, e):
        """开始分析"""
        code = self._stock_input.value.strip()
        if not code:
            self._show_result("请输入股票代码", is_error=True)
            return

        self._result_area.content = ft.Column([
            ft.ProgressRing(width=50, height=50),
            ft.Text(f"正在分析 {code}..."),
        ])
        self._result_area.update()

        # TODO: 接入 Pipeline
        # 模拟分析
        import time
        time.sleep(1)

        result = f"分析完成: {code}\n买入建议: 持有\n评分: 75分"
        self._show_result(result)

    def _show_result(self, message: str, is_error: bool = False):
        """显示结果"""
        color = "#f44336" if is_error else "#4caf50"
        self._result_area.content = ft.Text(message, color=color)
        self._result_area.update()
```

- [ ] **Step 2: Commit**

```bash
git add gui/pages/analyze.py && git commit -m "feat: add AnalyzePage (分析页)"
```

---

## Task 4: 创建 TasksPage（任务页）

**Files:**
- Create: `gui/pages/tasks.py`

- [ ] **Step 1: 创建 gui/pages/tasks.py**

```python
"""任务历史页面"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY

class TasksPage(ft.UserControl):
    """任务历史页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app

    def build(self):
        header = ft.Text("历史任务", size=24, weight=ft.FontWeight.BOLD)

        # 任务列表
        self.task_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
        )

        self._load_tasks()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                self.task_list,
            ]),
            padding=10,
        )

    def _load_tasks(self):
        """加载任务历史"""
        # TODO: 接入 TaskStore
        example_tasks = [
            ("600519", "2026-05-01 10:30", "完成", "75分"),
            ("000001", "2026-05-01 09:15", "完成", "68分"),
        ]
        for code, time_str, status, score in example_tasks:
            self.task_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{code}", weight=ft.FontWeight.BOLD),
                            ft.Text(time_str, color=TEXT_SECONDARY, size=12),
                        ]),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Text(status, color="#4caf50"),
                            padding=5,
                            bgcolor="#1b5e20",
                            border_radius=5,
                        ),
                        ft.Text(f"评分: {score}"),
                    ]),
                    padding=15,
                    bgcolor=CARD_BG,
                    border_radius=10,
                )
            )
```

- [ ] **Step 2: Commit**

```bash
git add gui/pages/tasks.py && git commit -m "feat: add TasksPage (任务页)"
```

---

## Task 5: 创建 ConfigPage（配置页）

**Files:**
- Create: `gui/pages/config.py`

- [ ] **Step 1: 创建 gui/pages/config.py`

```python
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

        # API 配置
        api_section = self._build_section("API 配置", [
            ("OpenAI API Key:", "输入你的 API Key"),
            ("API 地址:", "https://api.minimax.chat/v1"),
            ("模型名称:", "abab6-chat"),
        ])

        # 自选股配置
        stock_section = self._build_section("自选股配置", [
            ("股票列表:", "000001,600519,000002"),
        ])

        # 通知配置
        notify_section = self._build_section("通知配置", [
            ("企业微信:", "Webhook URL（可选）"),
            ("飞书:", "Webhook URL（可选）"),
        ])

        # 保存按钮
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
```

- [ ] **Step 2: Commit**

```bash
git add gui/pages/config.py && git commit -m "feat: add ConfigPage (配置页)"
```

---

## Task 6: 创建 LogsPage（日志页）

**Files:**
- Create: `gui/pages/logs.py`

- [ ] **Step 1: 创建 gui/pages/logs.py**

```python
"""日志页面"""
import flet as ft
from pathlib import Path
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY

class LogsPage(ft.UserControl):
    """日志查看页面"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._log_content = None

    def build(self):
        header = ft.Text("运行日志", size=24, weight=ft.FontWeight.BOLD)

        # 工具栏
        toolbar = ft.Row([
            ft.IconButton(
                icon=ft.icons.REFRESH,
                on_click=self._load_logs,
                tooltip="刷新",
            ),
        ])

        # 日志内容
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
                    content = latest_log.read_text(encoding="utf-8")
                    # 只显示最后 100 行
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
```

- [ ] **Step 2: Commit**

```bash
git add gui/pages/logs.py && git commit -m "feat: add LogsPage (日志页)"
```

---

## Task 7: 更新 main.py 支持 --gui 参数

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 更新 main.py 添加 --gui 参数**

在 `parse_arguments()` 函数中添加:
```python
parser.add_argument(
    '--gui',
    action='store_true',
    help='启动 Flet 桌面客户端',
)
```

- [ ] **Step 2: 在 main() 函数中添加启动逻辑**

```python
# === GUI 模式：启动 Flet 桌面客户端 ===
if args.gui:
    from gui.main import main as gui_main
    gui_main()
    return 0
```

- [ ] **Step 3: Commit**

```bash
git add main.py && git commit -m "feat: add --gui flag to main.py"
```

---

## Task 8: 更新打包配置

**Files:**
- Create: `gui/open-daily-stock.spec` (或更新现有 .spec)

- [ ] **Step 1: 创建 PyInstaller spec**

```python
# -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ['gui/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('data_provider', 'data_provider'),
    ],
    hiddenimports=['flet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='open-daily-stock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI 程序不需要控制台
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='open-daily-stock',
)
```

- [ ] **Step 2: 更新 .github/workflows/build.yml**

添加 GUI 打包步骤:
```yaml
- name: Build GUI executable
  run: |
    pip install flet>=0.25.0
    pyinstaller gui/open-daily-stock.spec
  if: matrix.os == 'windows-latest'
```

- [ ] **Step 3: Commit**

```bash
git add gui/open-daily-stock.spec .github/workflows/build.yml && git commit -m "feat: add PyInstaller config for Flet GUI"
```

---

## 执行顺序

1. Task 1: 创建 gui/ 目录结构
2. Task 2: MarketsPage（行情页）
3. Task 3: AnalyzePage（分析页）
4. Task 4: TasksPage（任务页）
5. Task 5: ConfigPage（配置页）
6. Task 6: LogsPage（日志页）
7. Task 7: 更新 main.py 支持 --gui
8. Task 8: 更新打包配置

---

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
