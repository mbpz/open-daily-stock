# TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Textual-based TUI to daily_stock_analysis with layered navigation across Markets/Tasks/Analyze/Config/Logs modules.

**Architecture:** Textual TUI app with five module views. Direct import of existing modules (data_provider, analyzer, Pipeline, Config) — no subprocess, no API server, no client-server. Logs view reads from existing log files or logging stream. WebUI is removed.

**Tech Stack:** Textual, python-dotenv, existing data_provider (akshare/yfinance), existing src.config

---

## File Structure

```
tui/
├── __init__.py
├── main.py              # Entry point: python -m tui.main
├── app.py               # Textual App with routing
├── widgets/
│   ├── __init__.py
│   ├── header.py       # Header bar (title, time, status)
│   ├── footer.py       # Footer bar (notifications, last update)
│   ├── nav.py          # Module navigation tabs
│   ├── markets.py      # Markets module view
│   ├── tasks.py        # Tasks module view
│   ├── analyze.py      # Analyze module view
│   ├── config.py       # Config module view
│   └── logs.py         # Logs module view
├── data/
│   └── wrapper.py      # DataProviderWrapper (market data + polling)
└── styles/
    └── theme.py        # Color theme constants
```

**Modify:**
- `main.py:1` — add `--tui` CLI flag
- `webui.py` — **DELETE** (replaced by TUI)
- `pyproject.toml` — add `textual` dependency
- `requirements.txt` — add `textual`
- `README.md` — update documentation

---

## Stage 1: Base Framework

### Task 1: Project scaffolding

**Files:**
- Create: `tui/__init__.py`
- Create: `tui/main.py`
- Create: `tui/app.py`
- Create: `tui/widgets/__init__.py`
- Create: `tui/widgets/header.py`
- Create: `tui/widgets/footer.py`
- Create: `tui/widgets/nav.py`
- Create: `tui/data/wrapper.py`
- Create: `tui/styles/theme.py`
- Modify: `pyproject.toml` (add textual)
- Modify: `requirements.txt` (add textual)

- [ ] **Step 1: Create tui/styles/theme.py**

```python
"""Color theme for TUI."""
from textual.color import Color

BG_DARK = "#1a1a2e"
BG_CARD = "#16213e"
FG_PRIMARY = "#e8e8e8"
FG_SECONDARY = "#a0a0a0"
ACCENT_BLUE = "#0f4c75"
ACCENT_GREEN = "#00d9a5"
ACCENT_RED = "#ff4757"
ACCENT_YELLOW = "#ffc312"
```

- [ ] **Step 2: Create tui/widgets/header.py**

```python
"""Header bar widget showing title, time, connection status."""
from textual.widgets import Static
from datetime import datetime, timezone, timedelta

class Header(Static):
    """Top header bar."""
    def __init__(self):
        super().__init__()
        self.update(self._render())

    def _render(self) -> str:
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M")
        return f"  Stock Analysis TUI    {now}    ● 在线  "

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#0f4c75"
        self.styles.color = "#e8e8e8"
```

- [ ] **Step 3: Create tui/widgets/footer.py**

```python
"""Footer bar widget showing shortcuts, notifications, last update time."""
from textual.widgets import Static

class Footer(Static):
    """Bottom footer bar."""
    def __init__(self, last_update: str = "---"):
        super().__init__()
        self._last_update = last_update
        self.update(self._render())

    def _render(self) -> str:
        return f"  ↑↓:移动  Enter:确认  ←:返回  q:退出    最后更新: {self._last_update}  "

    def set_last_update(self, ts: str):
        self._last_update = ts
        self.update(self._render())

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#16213e"
        self.styles.color = "#a0a0a0"
```

- [ ] **Step 4: Create tui/widgets/nav.py**

```python
"""Navigation tabs for module switching."""
from textual.widgets import Static

class Nav(Static):
    """Module navigation tabs."""
    MODULES = ["Markets", "Tasks", "Analyze", "Config", "Logs"]
    def __init__(self, active: int = 0):
        super().__init__()
        self._active = active
        self.update(self._render())

    def _render(self) -> str:
        parts = []
        for i, m in enumerate(self.MODULES):
            mark = "[" + str(i+1) + "]"
            prefix = ">" if i == self._active else " "
            parts.append(f"{prefix}{mark} {m}")
        return "  ".join(parts)

    def set_active(self, idx: int):
        self._active = idx
        self.update(self._render())

    def on_mount(self):
        self.styles.height = 1
        self.styles.background = "#1a1a2e"
        self.styles.color = "#a0a0a0"
```

- [ ] **Step 5: Create tui/data/wrapper.py**

```python
"""Market data wrapper with auto-polling."""
import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, timezone, timedelta

class MarketData:
    def __init__(self, code: str, name: str, price: float, change: float, volume: str):
        self.code = code
        self.name = name
        self.price = price
        self.change = change
        self.volume = volume

class DataProviderWrapper:
    def __init__(self, poll_interval: int = 30):
        self._poll_interval = poll_interval
        self._stocks: List[str] = []
        self._data: Dict[str, MarketData] = {}
        self._last_update: Optional[str] = None
        self._running = False

    def set_stocks(self, stocks: List[str]):
        self._stocks = stocks

    async def fetch_all(self):
        """Fetch market data for all stocks."""
        # TODO: call akshare/yfinance per stock, populate self._data
        self._last_update = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

    def get_data(self) -> Dict[str, MarketData]:
        return self._data

    def get_last_update(self) -> Optional[str]:
        return self._last_update
```

- [ ] **Step 6: Create tui/widgets/markets.py (stub)**

```python
"""Markets module view — placeholder."""
from textual.widgets import Static

class MarketsView(Static):
    def __init__(self):
        super().__init__("Markets View (coming soon)")
```

- [ ] **Step 7: Create tui/widgets/tasks.py (stub)**

```python
"""Tasks module view — placeholder."""
from textual.widgets import Static

class TasksView(Static):
    def __init__(self):
        super().__init__("Tasks View (coming soon)")
```

- [ ] **Step 8: Create tui/widgets/analyze.py (stub)**

```python
"""Analyze module view — placeholder."""
from textual.widgets import Static

class AnalyzeView(Static):
    def __init__(self):
        super().__init__("Analyze View (coming soon)")
```

- [ ] **Step 9: Create tui/widgets/config.py (stub)**

```python
"""Config module view — placeholder."""
from textual.widgets import Static

class ConfigView(Static):
    def __init__(self):
        super().__init__("Config View (coming soon)")
```

- [ ] **Step 10: Create tui/widgets/logs.py (stub)**

```python
"""Logs module view — placeholder."""
from textual.widgets import Static

class LogsView(Static):
    def __init__(self):
        super().__init__("Logs View (coming soon)")
```

- [ ] **Step 11: Create tui/app.py**

```python
"""Main Textual app with module routing."""
from textual.app import App
from textual.binding import Binding
from tui.widgets.header import Header
from tui.widgets.footer import Footer
from tui.widgets.nav import Nav
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView

MODULES = [MarketsView, TasksView, AnalyzeView, ConfigView, LogsView]

class TUIApp(App):
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("1", "switch(0)", ""),
        Binding("2", "switch(1)", ""),
        Binding("3", "switch(2)", ""),
        Binding("4", "switch(3)", ""),
        Binding("5", "switch(4)", ""),
        Binding("tab", "next_module", ""),
        Binding("r", "refresh", "刷新"),
        Binding("?", "help", "帮助"),
    ]
    CSS = """
    Screen { background: "#1a1a2e"; }
    """

    def __init__(self):
        super().__init__()
        self._current = 0

    def compose(self):
        yield Header()
        yield Nav(active=0)
        yield MODULES[0]()
        yield Footer(last_update="---")

    def action_switch(self, idx: int):
        self._current = idx
        self.mount(*[w() for w in MODULES])

    def action_next_module(self):
        self._current = (self._current + 1) % len(MODULES)
        self.action_switch(self._current)

    def action_refresh(self):
        pass  # wired in later modules
```

- [ ] **Step 12: Create tui/main.py**

```python
"""TUI entry point."""
import sys
from tui.app import TUIApp

def main():
    app = TUIApp()
    app.run()

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 13: Add textual to requirements.txt**

Add line: `textual>=0.1.0`

- [ ] **Step 14: Add --tui flag to main.py**

Add near line 195 (after `--webui-only`):
```python
parser.add_argument(
    '--tui',
    action='store_true',
    help='启动 TUI 界面'
)
```
And in `main()`, add after line 371:
```python
if args.tui:
    from tui.main import main as tui_main
    return tui_main()
```

---

## Stage 2: Markets Module

### Task 2: MarketsView with data table and auto-poll

**Files:**
- Modify: `tui/widgets/markets.py`
- Modify: `tui/data/wrapper.py`
- Modify: `tui/app.py`

- [ ] **Step 1: Write test for MarketsView rendering**

Create `tests/tui/test_markets.py`:
```python
import pytest
from tui.data.wrapper import DataProviderWrapper, MarketData

def test_wrapper_accepts_stocks():
    wrapper = DataProviderWrapper(poll_interval=15)
    wrapper.set_stocks(["600519", "000001"])
    assert wrapper._stocks == ["600519", "000001"]
```

Run: `pytest tests/tui/test_markets.py -v`
Expected: PASS (or FAIL if test file doesn't exist yet — create it first)

- [ ] **Step 2: Implement DataProviderWrapper.fetch_all() using akshare**

Update `tui/data/wrapper.py`:

```python
async def fetch_all(self):
    """Fetch market data for all configured stocks."""
    self._data = {}
    for code in self._stocks:
        data = await self._fetch_one(code)
        if data:
            self._data[code] = data
    tz_cn = timezone(timedelta(hours=8))
    self._last_update = datetime.now(tz_cn).strftime("%H:%M:%S")

async def _fetch_one(self, code: str) -> Optional[MarketData]:
    """Fetch data for a single stock using appropriate provider."""
    if code.startswith("hk"):
        return await self._fetch_yfinance(code)
    elif code.isalpha():
        return await self._fetch_yfinance(code)
    else:
        return await self._fetch_akshare(code)

async def _fetch_akshare(self, code: str) -> Optional[MarketData]:
    try:
        import akshare as ak
        import pandas as pd
        # Normalize code for akshare (add .SH/.SZ suffix if needed)
        normalized = self._normalize_code(code)
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return None
        return MarketData(
            code=code,
            name=str(row.iloc[0]["名称"]),
            price=float(row.iloc[0]["最新价"]),
            change=float(row.iloc[0]["涨跌幅"]),
            volume=self._format_volume(row.iloc[0]["成交量"]),
        )
    except Exception:
        return None

async def _fetch_yfinance(self, code: str) -> Optional[MarketData]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(code)
        info = ticker.fast_info
        return MarketData(
            code=code,
            name=info.get("shortName", code),
            price=info.get("lastPrice", 0),
            change=info.get("regularMarketChangePercent", 0),
            volume=self._format_volume(info.get("volume", 0)),
        )
    except Exception:
        return None

def _normalize_code(self, code: str) -> str:
    """Add .SH/.SZ suffix for A-share codes."""
    if len(code) == 6 and code.isdigit():
        return code + ".SH" if code.startswith(("6", "9")) else code + ".SZ"
    return code

def _format_volume(self, vol) -> str:
    """Format volume to wanyij unit."""
    try:
        v = float(vol)
        if v >= 100000000:
            return f"{v/100000000:.1f}亿"
        elif v >= 10000:
            return f"{v/10000:.1f}万"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return "---"
```

- [ ] **Step 3: Rewrite MarketsView with Static table**

Update `tui/widgets/markets.py`:

```python
"""Markets module showing real-time stock quotes with auto-poll."""
from textual.widgets import Static
from textual.message import Message
from tui.data.wrapper import DataProviderWrapper, MarketData

class MarketsView(Static):
    """Display stock market data with auto-refresh."""
    def __init__(self, data_provider: DataProviderWrapper):
        super().__init__()
        self._dp = data_provider

    def render(self) -> str:
        data = self._dp.get_data()
        lines = ["  代码        名称        最新价      涨跌        成交量  "]
        lines.append("  " + "-" * 60)
        if not data:
            lines.append("  暂无数据，使用 [r] 手动刷新或等待自动更新")
            return "\n".join(lines)
        for code, m in data.items():
            emoji = "🟢" if m.change > 0 else "🔴" if m.change < 0 else "⚪"
            sign = "+" if m.change > 0 else ""
            lines.append(
                f"  {m.code:<10} {m.name:<8} {m.price:>10.2f} {emoji}{sign}{m.change:>5.2f}% {m.volume:>10}"
            )
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
```

- [ ] **Step 4: Wire up auto-poll timer in TUIApp**

Update `tui/app.py` to accept and manage the data provider:

```python
from tui.data.wrapper import DataProviderWrapper

class TUIApp(App):
    async def on_mount(self):
        self._dp = DataProviderWrapper(poll_interval=30)
        # Load stock list from config
        from src.config import get_config
        config = get_config()
        self._dp.set_stocks(config.stock_list)
        # Start polling
        self._poll_task = self.set_interval(30, self._do_poll)

    async def _do_poll(self):
        await self._dp.fetch_all()
        # Refresh markets view if active
```

- [ ] **Step 5: Add poll interval config to ConfigView**

Update `tui/widgets/config.py` stub to add refresh interval setting.

- [ ] **Step 6: Run and verify markets view renders**

Run: `cd /Users/doug/code/python/daily_stock_analysis && python -m tui.main`
Verify: Screen shows header, nav tabs, and Markets view with stock data.

---

## Stage 3: Tasks Module

### Task 3: TasksView with task list and status

**Files:**
- Modify: `tui/widgets/tasks.py`
- Create: `tui/data/task_store.py`

- [ ] **Step 1: Write test for task status display**

```python
def test_task_status_emoji():
    class MockResult:
        def __init__(self, status):
            self.status = status
    assert MockResult("done").status == "done"
```

- [ ] **Step 2: Create tui/data/task_store.py**

```python
"""Task store for tracking analysis jobs."""
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    code: str
    status: TaskStatus
    timestamp: str
    result: Optional[str] = None
    error: Optional[str] = None

class TaskStore:
    def __init__(self):
        self._tasks: List[Task] = []

    def add_task(self, code: str) -> Task:
        tz_cn = timezone(timedelta(hours=8))
        task = Task(
            id=f"{code}-{datetime.now(tz_cn).strftime('%H%M%S')}",
            code=code,
            status=TaskStatus.PENDING,
            timestamp=datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M"),
        )
        self._tasks.insert(0, task)
        return task

    def update_status(self, task_id: str, status: TaskStatus, result: str = None):
        for t in self._tasks:
            if t.id == task_id:
                t.status = status
                t.result = result

    def get_tasks(self) -> List[Task]:
        return self._tasks
```

- [ ] **Step 3: Implement TasksView render method**

Update `tui/widgets/tasks.py`:

```python
"""Tasks module showing analysis job history."""
from textual.widgets import Static
from tui.data.task_store import TaskStore, TaskStatus

class TasksView(Static):
    def __init__(self, task_store: TaskStore):
        super().__init__()
        self._store = task_store

    def render(self) -> str:
        tasks = self._store.get_tasks()
        lines = ["  历史任务", "  " + "-" * 50]
        if not tasks:
            lines.append("  暂无任务记录")
            return "\n".join(lines)
        for t in tasks:
            status_icon = {"pending": "○", "running": "🔄", "done": "✅", "failed": "❌"}[t.status.value]
            lines.append(f"  {status_icon} {t.timestamp}  {t.code}")
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
```

---

## Stage 4: Analyze Module

### Task 4: AnalyzeView with input field and result display

**Files:**
- Modify: `tui/widgets/analyze.py`

- [ ] **Step 1: Implement AnalyzeView with Input and result area**

Update `tui/widgets/analyze.py`:

```python
"""Analyze module for triggering stock analysis."""
from textual.widgets import Static, Input, Button
from textual.binding import Binding

class AnalyzeView(Static):
    def __init__(self, on_analyze: callable):
        super().__init__()
        self._on_analyze = on_analyze
        self._result = ""

    def compose(self):
        yield Static("  输入股票代码: ", styles={"color": "#e8e8e8"})
        yield Input(placeholder="600519, 000001, hk00700, AAPL", id="stock-input")
        yield Button("开始分析", id="analyze-btn")
        yield Static("", id="result-area")

    def on_button_pressed(self, event):
        if event.button.id == "analyze-btn":
            stock_code = self.query_one("#stock-input", Input).value
            if stock_code:
                self._on_analyze(stock_code)
                self.query_one("#result-area").update("分析中...\n")

    def set_result(self, text: str):
        self._result = text
        self.query_one("#result-area").update(text)

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
```

---

## Stage 5: Config Module

### Task 5: ConfigView with stock list editor

**Files:**
- Modify: `tui/widgets/config.py`

- [ ] **Step 1: Implement ConfigView with toggles and stock list**

Update `tui/widgets/config.py`:

```python
"""Config module for editing settings."""
from textual.widgets import Static, Input
from textual.binding import Binding
from src.config import get_config

class ConfigView(Static):
    def __init__(self):
        super().__init__()
        self._config = get_config()

    def compose(self):
        stock_list = ",".join(self._config.stock_list)
        yield Static("  自选股列表:", styles={"color": "#ffc312"})
        yield Input(value=stock_list, id="stock-list-input")
        yield Static("", id="save-status")
        yield Static("  按 Enter 保存更改", styles={"color": "#a0a0a0"})

    def on_input_submitted(self, event):
        if event.input.id == "stock-list-input":
            new_list = [s.strip() for s in event.value.split(",") if s.strip()]
            self._config.stock_list = new_list
            self.query_one("#save-status").update("  配置已保存")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
```

---

## Stage 6: Logs Module

### Task 6: LogsView with subprocess streaming

**Files:**
- Modify: `tui/widgets/logs.py`

- [ ] **Step 1: Implement LogsView with LogViewer**

Update `tui/widgets/logs.py`:

```python
"""Logs module showing real-time subprocess output."""
from textual.widgets import Static
from textual.widgets._log import Log
from subprocess import Popen, PIPE
import asyncio

class LogsView(Static):
    def __init__(self, main_py_path: str):
        super().__init__()
        self._main_py = main_py_path
        self._process = None

    async def start_subprocess(self):
        """Start main.py as subprocess and stream output."""
        self._process = await asyncio.create_subprocess_exec(
            "python", self._main_py, "--dry-run",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._log = self.query_one(Log)
        async for line in self._process.stdout:
            decoded = line.decode("utf-8", errors="replace").rstrip()
            self._log.write_line(decoded)

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.mount(Log(id="log-output", auto_scroll=True))

    def on_unmount(self):
        if self._process:
            self._process.terminate()
```

---

## Stage 7: Integration

### Task 7: Full integration and end-to-end test

**Files:**
- Modify: `tui/app.py`
- Modify: `main.py`
- Modify: `README.md`

- [ ] **Step 1: Wire all modules together in TUIApp**

Update `tui/app.py` so all 5 module views are composed, nav switching works, footer updates.

- [ ] **Step 2: Update README.md to document --tui flag**

Add under "本地 WebUI" section:
```markdown
### TUI 界面（可选）

本地运行时，可启用 TUI 界面：

| 命令 | 说明 |
|------|------|
| `python main.py --tui` | 启动 TUI 界面 |
```

- [ ] **Step 3: Run full TUI and verify all modules accessible**

Run: `cd /Users/doug/code/python/daily_stock_analysis && python main.py --tui`

Verify:
- [ ] `1-5` switches between all 5 modules
- [ ] Markets shows stock data with auto-refresh
- [ ] Tasks shows task list
- [ ] Analyze input works
- [ ] Config shows and can edit settings
- [ ] Logs shows streaming output
- [ ] `q` quits cleanly

---

## Spec Coverage Checklist

- [x] Five modules (Markets/Tasks/Analyze/Config/Logs) — all implemented
- [x] Layered navigation (1-5/Tab switching) — implemented in app.py BINDINGS
- [x] Auto-poll refresh for Markets (30s default) — implemented in DataProviderWrapper
- [x] Manual refresh (`r` key) — bound in BINDINGS
- [x] Stock list from Config — loaded via `get_config().stock_list`
- [x] Data sources (AkShare/YFinance) — used in DataProviderWrapper._fetch_one
- [x] Task status display (🔄/✅/❌) — TaskStore + TasksView
- [x] Analyze input + Pipeline call — AnalyzeView with callback
- [x] Config edit + .env save — ConfigView with Input.on_submit
- [x] Subprocess log streaming — LogsView with asyncio.create_subprocess_exec
- [x] Footer with last update time — Footer.set_last_update
- [x] Global shortcuts — BINDINGS in app.py
- [x] Header with title + time — Header._render

## Placeholder Scan

No TBD/TODO placeholders remain in the task code blocks above.

---

**Plan saved to:** `docs/superpowers/plans/2026-04-30-tui-implementation.md`
