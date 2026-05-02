# PC Client 架构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 TUI + GUI 双模式 PC 客户端，共享 DataService 后端守护进程

**Architecture:**
- main.py 是唯一入口，自动 fork DataService 子进程
- TUI/GUI 作为客户端通过 stdio JSON 与 DataService 通信
- DataService 定时拉取数据，主动推送给客户端
- SQLite 本地缓存，config.json 配置管理

**Tech Stack:** Python subprocess, JSON, SQLite, Textual, Flet

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/data_service.py` | Create | 后端守护进程，数据拉取/缓存/推送 |
| `src/service_client.py` | Create | 客户端通信库，TUI/GUI 公用 |
| `main.py` | Modify | 进程管理，fork DataService，选择 TUI/GUI |
| `src/config.py` | Modify | 添加 config.json 读写 |
| `tests/test_data_service.py` | Create | DataService 测试 |
| `tests/test_service_client.py` | Create | ServiceClient 测试 |

---

## Task 1: DataService 后端实现

**Files:**
- Create: `src/data_service.py`
- Create: `tests/test_data_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_service.py
import pytest
import json
import subprocess
import sys
import time

class TestDataService:
    def test_data_service_starts(self):
        """DataService 进程可以启动并响应 hello 请求"""
        proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # 发送 hello 请求
        req = json.dumps({"action": "hello"})
        proc.stdin.write(req.encode())
        proc.stdin.flush()

        # 读取响应
        line = proc.stdout.readline()
        resp = json.loads(line)

        proc.terminate()
        assert resp.get("status") == "ok"
        assert "version" in resp

    def test_get_markets_request(self):
        """DataService 可以响应 get_markets 请求"""
        # 类似上面的测试，但发送 get_markets
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_service.py -v`
Expected: ImportError 或 process 启动失败

- [ ] **Step 3: Write minimal DataService**

```python
# src/data_service.py
"""DataService 后端守护进程"""
import json
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

class DataService:
    def __init__(self):
        self._running = True
        self._db_path = ".open-daily-stock.db"
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                code TEXT PRIMARY KEY,
                name TEXT,
                price REAL,
                change_pct REAL,
                volume INTEGER,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _send(self, data: Dict[str, Any]):
        """发送 JSON 到 stdout"""
        print(json.dumps(data), flush=True)

    def _handle_request(self, req: Dict[str, Any]):
        """处理请求"""
        action = req.get("action", "")

        if action == "hello":
            self._send({"status": "ok", "version": "0.3.0"})
        elif action == "get_markets":
            markets = self._get_markets()
            self._send({"status": "ok", "data": markets})
        elif action == "refresh":
            self._refresh_markets()
            self._send({"status": "ok", "message": "refreshed"})
        elif action == "quit":
            self._running = False
        else:
            self._send({"status": "error", "message": f"unknown action: {action}"})

    def _get_markets(self):
        """从数据库获取行情数据"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("SELECT code, name, price, change_pct, volume FROM markets")
        rows = c.fetchall()
        conn.close()
        return [{"code": r[0], "name": r[1], "price": r[2], "change_pct": r[3], "volume": r[4]} for r in rows]

    def _refresh_markets(self):
        """刷新行情数据（TODO: 调用 AkShare/YFinance）"""
        pass

    def run(self):
        """主循环：读取 stdin，处理请求"""
        while self._running:
            line = sys.stdin.readline()
            if not line:
                break
            try:
                req = json.loads(line)
                self._handle_request(req)
            except json.JSONDecodeError:
                self._send({"status": "error", "message": "invalid json"})
            except Exception as e:
                self._send({"status": "error", "message": str(e)})

if __name__ == "__main__":
    service = DataService()
    service.run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add DataService backend process"
```

---

## Task 2: ServiceClient 客户端通信库

**Files:**
- Create: `src/service_client.py`
- Create: `tests/test_service_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_service_client.py
import pytest
from unittest.mock import patch, MagicMock

class TestServiceClient:
    def test_client_initialization(self):
        """ServiceClient 可以初始化并连接 DataService"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            client = ServiceClient()
            assert client._proc is not None
            mock_popen.assert_called_once()

    def test_hello(self):
        """ServiceClient.hello() 返回版本信息"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout.readline.return_value = '{"status": "ok", "version": "0.3.0"}'
            mock_popen.return_value = mock_proc

            client = ServiceClient()
            resp = client.hello()
            assert resp["version"] == "0.3.0"

    def test_get_markets(self):
        """ServiceClient.get_markets() 返回行情数据"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout.readline.return_value = '{"status": "ok", "data": []}'
            mock_popen.return_value = mock_proc

            client = ServiceClient()
            markets = client.get_markets()
            assert isinstance(markets, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_service_client.py -v`
Expected: ImportError

- [ ] **Step 3: Write ServiceClient**

```python
# src/service_client.py
"""ServiceClient - TUI/GUI 与 DataService 通信的客户端库"""
import json
import subprocess
import sys
from typing import Dict, Any, List, Optional

class ServiceClient:
    """客户端与 DataService 通信"""

    def __init__(self):
        self._proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def _send_request(self, action: str, data: Optional[Dict] = None) -> Dict:
        """发送请求到 DataService"""
        req = {"action": action}
        if data:
            req.update(data)

        self._proc.stdin.write(json.dumps(req).encode())
        self._proc.stdin.flush()

        line = self._proc.stdout.readline()
        return json.loads(line)

    def hello(self) -> Dict[str, Any]:
        """测试连接，返回版本"""
        return self._send_request("hello")

    def get_markets(self) -> List[Dict]:
        """获取行情数据"""
        resp = self._send_request("get_markets")
        return resp.get("data", [])

    def refresh(self) -> bool:
        """刷新行情数据"""
        resp = self._send_request("refresh")
        return resp.get("status") == "ok"

    def analyze(self, code: str) -> Dict[str, Any]:
        """分析股票"""
        return self._send_request("analyze", {"code": code})

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._send_request("get_config")

    def update_config(self, config: Dict) -> bool:
        """更新配置"""
        resp = self._send_request("update_config", {"data": config})
        return resp.get("status") == "ok"

    def quit(self):
        """关闭 DataService"""
        try:
            self._send_request("quit")
        except:
            pass
        self._proc.terminate()

    def __del__(self):
        """析构时确保进程关闭"""
        if hasattr(self, '_proc') and self._proc:
            self.quit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_service_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/service_client.py tests/test_service_client.py
git commit -m "feat: add ServiceClient for DataService communication"
```

---

## Task 3: main.py 进程管理

**Files:**
- Modify: `main.py` - 添加 DataService fork 逻辑

- [ ] **Step 1: Read current main.py structure**

了解 main.py 当前如何选择 TUI/GUI 模式

- [ ] **Step 2: Add DataService fork logic**

在 `main.py` 添加：

```python
import subprocess
import sys

_data_service_proc = None

def start_data_service():
    """启动 DataService 后端进程"""
    global _data_service_proc
    if _data_service_proc is None:
        _data_service_proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    return _data_service_proc

def stop_data_service():
    """关闭 DataService 后端进程"""
    global _data_service_proc
    if _data_service_proc:
        try:
            _data_service_proc.terminate()
        except:
            pass
        _data_service_proc = None

# 在 main() 开头调用
# start_data_service()
```

- [ ] **Step 3: Modify mode selection to use DataService**

```python
def main() -> int:
    args = parse_arguments()

    # 启动 DataService
    start_data_service()

    # 根据参数选择模式
    if args.tui:
        from tui.app import main as tui_main
        return tui_main()
    elif args.gui:
        from gui.main import main as gui_main
        return gui_main()
    else:
        # 默认 GUI
        from gui.main import main as gui_main
        return gui_main()
```

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add DataService process management in main.py"
```

---

## Task 4: TUI 集成 DataService

**Files:**
- Modify: `tui/app.py` - 使用 ServiceClient 获取数据
- Modify: `tui/data/wrapper.py` - 改为调用 ServiceClient

- [ ] **Step 1: Update TUIApp to use ServiceClient**

在 `TUIApp.__init__` 中：

```python
from src.service_client import ServiceClient

class TUIApp(App):
    def __init__(self):
        super().__init__()
        self._client = ServiceClient()
        # 获取初始数据
        self._markets = self._client.get_markets()
```

- [ ] **Step 2: Update DataProviderWrapper**

让 `DataProviderWrapper` 内部调用 `ServiceClient`

- [ ] **Step 3: Commit**

```bash
git add tui/app.py tui/data/wrapper.py
git commit -m "feat(tui): integrate ServiceClient for DataService communication"
```

---

## Task 5: GUI 集成 DataService

**Files:**
- Modify: `gui/app.py` - 使用 ServiceClient 获取数据
- Modify: `gui/pages/markets.py` - 改为调用 ServiceClient

- [ ] **Step 1: Update StockApp to use ServiceClient**

在 `StockApp.__init__` 中：

```python
from src.service_client import ServiceClient

class StockApp:
    def __init__(self, page):
        self._client = ServiceClient()
        self._markets = self._client.get_markets()
```

- [ ] **Step 2: Update GUI data fetching**

让 GUI 页面调用 `ServiceClient` 而不是直接调用 `DataProviderWrapper`

- [ ] **Step 3: Commit**

```bash
git add gui/app.py gui/pages/markets.py
git commit -m "feat(gui): integrate ServiceClient for DataService communication"
```

---

## Task 6: 首次启动引导

**Files:**
- Create: `src/setup_wizard.py`
- Modify: `main.py` - 检测配置文件并引导

- [ ] **Step 1: Create setup wizard**

```python
# src/setup_wizard.py
"""首次启动引导 - 配置 API keys 和自选股"""
import getpass

def run_wizard():
    """交互式引导配置"""
    print("=" * 50)
    print("首次使用配置")
    print("=" * 50)

    # API Keys
    gemini_key = getpass.getpass("Gemini API Key: ")
    deepseek_key = getpass.getpass("DeepSeek API Key: ")

    # 自选股
    stocks_input = input("自选股代码（逗号分隔，如 600519,000001）: ")
    stocks = [s.strip() for s in stocks_input.split(",") if s.strip()]

    # 保存配置
    config = {
        "stocks": stocks,
        "apis": {
            "gemini_key": gemini_key,
            "deepseek_key": deepseek_key
        }
    }

    import json
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("配置已保存！")
    return config
```

- [ ] **Step 2: Update main.py to check config**

```python
def main():
    # 检查是否需要引导
    if not os.path.exists("config.json"):
        from src.setup_wizard import run_wizard
        run_wizard()

    # 继续启动...
```

- [ ] **Step 3: Commit**

```bash
git add src/setup_wizard.py main.py
git commit -m "feat: add first-run setup wizard"
```

---

## Task 7: DataService 集成 AkShare/YFinance

**Files:**
- Modify: `src/data_service.py` - 添加真实数据拉取

- [ ] **Step 1: Update DataService._refresh_markets()**

```python
def _refresh_markets(self):
    """刷新行情数据"""
    from data_provider.efinance_fetcher import EfinanceFetcher
    from data_provider.akshare_fetcher import AkshareFetcher

    fetcher = AkshareFetcher()
    # ... 使用 fetcher 获取数据并写入 SQLite
```

- [ ] **Step 2: Commit**

```bash
git add src/data_service.py
git commit -m "feat: integrate AkShare/YFinance in DataService"
```

---

## Task 8: 完整集成测试

- [ ] **Step 1: 测试 TUI 模式**

```bash
python main.py --tui
# 验证：行情显示、刷新、分析功能正常
```

- [ ] **Step 2: 测试 GUI 模式**

```bash
python main.py --gui
# 验证：图形界面正常显示和交互
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: complete PC client integration"
```

---

## Verification

After all tasks complete:

1. `pytest tests/ -v` → All pass
2. `python main.py --gui` → GUI 打开并显示数据
3. `python main.py --tui` → TUI 正常启动
4. 首次运行无 config.json → 引导启动

---

**Plan complete. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review
- 多个 subagent 可以并行处理独立任务（如 Task 4 和 Task 5 可以同时进行）

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints for review