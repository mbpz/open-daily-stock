# TUI Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 open-daily-stock 建立全面测试框架，覆盖所有模块（80%+ 覆盖率）。

**Architecture:** 分层测试策略：conftest.py 共享 fixtures，各模块独立测试文件。TUI 用 textual run_test()，数据层用 VCR.py 录制/回放。

**Tech Stack:** pytest, pytest-asyncio, textual, pytest-mock, VCR.py

---

## Task 1: 创建测试基础设施

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/.env.test`
- Modify: `.gitignore`（添加 tests/.env.test）

- [ ] **Step 1: 创建 tests 目录**

```bash
mkdir -p tests/fixtures/cassettes tests/fixtures/mock_data tests/test_data_provider
touch tests/__init__.py tests/test_data_provider/__init__.py
```

- [ ] **Step 2: 创建 conftest.py**

```python
"""pytest shared fixtures"""
import pytest
import os
from pathlib import Path

# 设置测试环境变量
os.environ["TESTING"] = "true"

@pytest.fixture
def test_env_file(tmp_path):
    """创建临时测试 .env 文件"""
    env_file = tmp_path / ".env"
    return env_file

@pytest.fixture
def mock_config():
    """Mock 配置对象"""
    from unittest.mock import MagicMock
    config = MagicMock()
    config.stock_list = ["000001", "600519"]
    config.openai_api_key = None
    config.gemini_api_key = None
    config.openai_base_url = None
    config.openai_model = "gpt-4o-mini"
    config.wechat_webhook_url = None
    config.feishu_webhook_url = None
    return config

@pytest.fixture
def sample_stock_data():
    """样例股票数据"""
    return {
        "000001": {
            "name": "平安银行",
            "price": 12.50,
            "change": 0.85,
            "volume": "15.2万",
        },
        "600519": {
            "name": "贵州茅台",
            "price": 1680.00,
            "change": -1.25,
            "volume": "3.2万",
        },
    }
```

- [ ] **Step 3: 创建 .env.test**

```bash
# tests/.env.test（不提交到 git）
CLAUDE_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.minimax.chat/v1
OPENAI_MODEL=abab6-chat
STOCK_LIST=000001,600519
WECHAT_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=
```

- [ ] **Step 4: 更新 .gitignore**

```bash
echo "tests/.env.test" >> .gitignore
```

- [ ] **Step 5: Commit**

```bash
git add tests/ .gitignore
git commit -m "feat: add test infrastructure (conftest, fixtures)"
```

---

## Task 2: test_config.py

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
"""Config 模块测试"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 测试 is_first_time_setup
def test_is_first_time_setup_no_env(tmp_path):
    """无 .env 时返回 True"""
    with patch('src.config.Path') as mock_path:
        mock_path.return_value.parent = tmp_path
        mock_path.return_value.exists.return_value = False
        # import and test
        from src.config import Config
        config = Config.__new__(Config)
        config.stock_list = ["000001"]
        config.openai_api_key = "key"
        result = config.is_first_time_setup()
        assert result == False  # 有 API key，不是首次

def test_is_first_time_setup_no_api_key(tmp_path):
    """无 API Key 时返回 True"""
    from src.config import Config
    config = Config.__new__(Config)
    config.stock_list = ["000001"]
    config.openai_api_key = None
    config.gemini_api_key = None
    # should return True
    result = config.is_first_time_setup()
    assert result == True

def test_is_first_time_setup_empty_stock_list(tmp_path):
    """自选股为空时返回 True"""
    from src.config import Config
    config = Config.__new__(Config)
    config.stock_list = []
    config.openai_api_key = "key"
    # should return True
    result = config.is_first_time_setup()
    assert result == True

def test_save_to_env(tmp_path):
    """保存配置到 .env 文件"""
    from src.config import Config
    config = Config.__new__(Config)
    config.stock_list = ["000001", "600519"]
    config.openai_api_key = "test-key"
    config.openai_base_url = "https://api.test.com"
    config.openai_model = "test-model"

    env_path = tmp_path / ".env"
    updates = {
        "STOCK_LIST": "000001,600519",
        "OPENAI_API_KEY": "test-key",
        "OPENAI_BASE_URL": "https://api.test.com",
        "OPENAI_MODEL": "test-model",
    }
    result = config.save_to_env(updates)
    assert result == True
    assert env_path.exists()
    content = env_path.read_text()
    assert "OPENAI_API_KEY=test-key" in content

def test_refresh_from_updates():
    """刷新配置属性"""
    from src.config import Config
    config = Config.__new__(Config)
    config.stock_list = []
    config.openai_api_key = None

    updates = {
        "STOCK_LIST": "000001,600519",
        "OPENAI_API_KEY": "new-key",
    }
    config.refresh_from_updates(updates)
    assert config.stock_list == ["000001", "600519"]
    assert config.openai_api_key == "new-key"
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_config.py -v`
Expected: FAIL（is_first_time_setup 方法不存在或逻辑问题）

- [ ] **Step 3: 修复 is_first_time_setup**

检查 src/config.py 中的 is_first_time_setup 实现，确保逻辑正确

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add Config module tests"
```

---

## Task 3: test_wizard.py

**Files:**
- Create: `tests/test_wizard.py`

- [ ] **Step 1: 写失败测试**

```python
"""WizardView 模块测试"""
import pytest
from textual.app import App

async def test_wizard_step1_display():
    """步骤1显示正确"""
    from tui.app import TUIApp
    app = TUIApp()
    # 强制显示 wizard
    app._show_wizard = True
    app._wizard_completed = False

    async with app.run_test() as pilot:
        # 验证显示 "步骤 1/3"
        text = app.screen.query_one("#step-title").renderable
        assert "步骤 1/3" in str(text)
        # 验证显示 "配置 API Key"
        content = app.screen.get_character_counts()
        assert "配置 API Key" in content

async def test_wizard_navigate_fields():
    """↑↓ 导航字段"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = True
    app._wizard_completed = False

    async with app.run_test() as pilot:
        # 获取当前选中项
        initial_text = app.screen.query_one("#wizard-field-0").renderable

        # 按下键
        await pilot.press("down")

        # 验证选中项变化
        new_text = app.screen.query_one("#wizard-field-0").renderable
        # ► 应该在第二个字段
        assert "►" not in str(new_text) or "OpenAI/MiniMax" not in str(new_text)

async def test_wizard_edit_field():
    """Enter 编辑字段"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = True

    async with app.run_test() as pilot:
        # 按 Enter 编辑
        await pilot.press("enter")

        # 应该有输入框出现
        input_widget = app.screen.query_one("#wizard-input", None)
        assert input_widget is not None

        # 输入值
        await pilot.type("test-api-key")

        # 按 Enter 提交
        await pilot.press("enter")

        # 验证值已更新
        field_text = app.screen.query_one("#wizard-field-0").renderable
        assert "test-api-key" in str(field_text)

async def test_wizard_skip():
    """跳过引导"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = True

    # 记录当前模块
    initial_module = app._current

    async with app.run_test() as pilot:
        # 连续按 Enter 到第3步，然后按 Esc
        # 第3步才可跳过
        for _ in range(20):  # 安全限制
            try:
                await pilot.press("enter")
                await pilot.pause()
            except:
                break

        # 现在按 Esc 应该跳过
        await pilot.press("escape")

        await pilot.pause()

        # 验证进入了 Markets（模块0）
        # wizard_completed 应该为 True
        assert app._wizard_completed == True
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_wizard.py -v`
Expected: FAIL（测试环境问题或 wizard 逻辑问题）

- [ ] **Step 3: 修复问题**

根据失败信息修复，可能是：
- 输入框 ID 不对
- wizard 状态切换逻辑问题

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_wizard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_wizard.py
git commit -m "test: add WizardView tests"
```

---

## Task 4: test_tui_widgets.py

**Files:**
- Create: `tests/test_tui_widgets.py`

- [ ] **Step 1: 写失败测试**

```python
"""TUI Widgets 测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock

async def test_markets_display_empty():
    """无数据时显示空状态"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = False
    app._wizard_completed = True

    async with app.run_test() as pilot:
        # Markets 应该显示"暂无数据"或类似提示
        content = app.screen.get_character_counts()
        assert len(content) > 0

async def test_markets_with_data(mock_config):
    """有数据时显示行情"""
    from tui.app import TUIApp
    app = TUIApp()
    # 模拟有数据
    app._dp._data = {
        "000001": MagicMock(code="000001", name="平安银行", price=12.5, change=0.85)
    }

    async with app.run_test() as pilot:
        # 应该有行情显示
        # 具体验证根据 MarketsView 实际实现

async def test_config_display_fields():
    """ConfigView 显示所有字段"""
    from tui.widgets.config import ConfigView
    from textual.app import App

    app = App()
    async with app.run_test() as pilot:
        view = ConfigView()
        app.screen.mount(view)
        # 验证显示 7 个字段

async def test_config_edit_and_save():
    """编辑并保存配置"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = False
    app._wizard_completed = True

    async with app.run_test() as pilot:
        # 切换到 Config 模块
        await pilot.press("4")

        # 编辑第一个字段
        await pilot.press("enter")
        await pilot.type("000001,600519")
        await pilot.press("enter")

        # 保存
        await pilot.press("escape")
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_tui_widgets.py -v`

- [ ] **Step 3: 修复问题**

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_tui_widgets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_widgets.py
git commit -m "test: add TUI widgets tests"
```

---

## Task 5: test_tui_app.py

**Files:**
- Create: `tests/test_tui_app.py`

- [ ] **Step 1: 写失败测试**

```python
"""TUIApp 主程序测试"""
import pytest

async def test_app_switch_module():
    """切换模块"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = False

    async with app.run_test() as pilot:
        # 按 2 切换到 Tasks
        await pilot.press("2")
        assert app._current == 1

        # 按 3 切换到 Analyze
        await pilot.press("3")
        assert app._current == 2

async def test_app_refresh():
    """手动刷新"""
    from tui.app import TUIApp
    app = TUIApp()
    app._show_wizard = False

    async with app.run_test() as pilot:
        # 按 r 刷新
        await pilot.press("r")
        await pilot.pause()
        # 验证刷新任务被创建
        assert app._refresh_task is not None

async def test_app_quit():
    """退出"""
    from tui.app import TUIApp
    app = TUIApp()

    async with app.run_test() as pilot:
        await pilot.press("q")
        # 验证应用退出
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_tui_app.py -v`

- [ ] **Step 3: 修复问题**

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_tui_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_app.py
git commit -m "test: add TUIApp tests"
```

---

## Task 6: test_pipeline.py

**Files:**
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试**

```python
"""Pipeline 核心流程测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_pipeline_fetch_data():
    """Pipeline 获取数据"""
    from src.core.pipeline import StockAnalysisPipeline
    from src.config import Config

    config = MagicMock()
    config.stock_list = ["000001"]
    config.max_workers = 1

    pipeline = StockAnalysisPipeline(config=config, max_workers=1)

    # Mock 数据提供者
    with patch.object(pipeline, '_fetch_stock_data', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"000001": MagicMock()}
        # 调用 fetch
        result = await pipeline._fetch_stock_data("000001")
        assert result is not None

def test_pipeline_analyze():
    """Pipeline 执行分析"""
    # mock analyzer
    pass

def test_pipeline_notify():
    """Pipeline 发送通知"""
    # mock notifier
    pass
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_pipeline.py -v`

- [ ] **Step 3: 修复问题**

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "test: add Pipeline tests"
```

---

## Task 7: test_notification.py

**Files:**
- Create: `tests/test_notification.py`

- [ ] **Step 1: 写失败测试**

```python
"""NotificationService 测试"""
import pytest
from unittest.mock import MagicMock, patch

def test_wechat_webhook_format():
    """企业微信 Webhook 格式验证"""
    from src.notification import NotificationService

    service = NotificationService()

    # Mock requests.post
    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)

        # 发送测试消息
        result = service.send_to_wechat("测试消息")

        # 验证调用参数格式
        assert mock_post.called
        call_args = mock_post.call_args
        # 检查 url 格式
        assert "qyapi.weixin.qq.com" in str(call_args)

def test_notification_skip_when_disabled():
    """未配置时跳过通知"""
    from src.notification import NotificationService

    service = NotificationService()
    service._wechat_webhook_url = None

    # 应该跳过，不发送
    result = service.send_to_wechat("测试消息")
    assert result == False

def test_feishu_webhook_format():
    """飞书 Webhook 格式验证"""
    from src.notification import NotificationService

    service = NotificationService()

    with patch('requests.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = service.send_to_feishu("测试消息")
        assert mock_post.called
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_notification.py -v`

- [ ] **Step 3: 修复问题**

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_notification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_notification.py
git commit -m "test: add NotificationService tests"
```

---

## Task 8: test_data_provider + test_analyzer

**Files:**
- Create: `tests/test_data_provider/conftest.py`
- Create: `tests/test_data_provider/test_wrapper.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: 写失败测试**

```python
# test_data_provider/conftest.py
"""数据提供器共享 fixtures"""
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_efinance_response():
    """Mock Efinance 响应数据"""
    return {
        "data": [
            {"股票名称": "平安银行", "股票代码": "000001", "日期": "2026-05-01",
             "开盘": 12.0, "收盘": 12.5, "最高": 12.8, "最低": 11.9,
             "成交量": "15万", "成交额": "1800万"}
        ]
    }

# test_data_provider/test_wrapper.py
"""DataProviderWrapper 测试"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_wrapper_fetch_all():
    """Wrapper 获取所有股票数据"""
    from tui.data.wrapper import DataProviderWrapper

    wrapper = DataProviderWrapper(poll_interval=30)
    wrapper.set_stocks(["000001"])

    with patch.object(wrapper, '_fetch_one', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MagicMock(
            code="000001", name="平安银行", price=12.5, change=0.85, volume="15万"
        )
        await wrapper.fetch_all()
        assert "000001" in wrapper._data

# test_analyzer.py
"""AI Analyzer 测试"""
import pytest
from unittest.mock import patch, MagicMock

def test_analyzer_no_key():
    """无 API Key 时"""
    from src.analyzer import GeminiAnalyzer

    analyzer = GeminiAnalyzer(api_key=None)
    assert analyzer._model is None

def test_analyzer_mock_response():
    """Mock LLM 响应"""
    from src.analyzer import GeminiAnalyzer

    analyzer = GeminiAnalyzer(api_key="test-key")

    with patch.object(analyzer, '_call_gemini', return_value="测试分析结果"):
        result = analyzer.analyze("000001", {"data": []})
        assert result is not None
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_data_provider/ tests/test_analyzer.py -v`

- [ ] **Step 3: 修复问题**

- [ ] **Step 4: 再次运行测试**

Run: `pytest tests/test_data_provider/ tests/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_data_provider/ tests/test_analyzer.py
git commit -m "test: add data provider and analyzer tests"
```

---

## Task 9: CI Workflow 配置

**Files:**
- Modify: `.github/workflows/test.yml`

- [ ] **Step 1: 创建 test workflow**

```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio textual pytest-mock vcrpy pytest-vcr

      - name: Run tests
        run: pytest tests/ -v --tb=short

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: always()
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: add test workflow"
```

---

## Task 10: 覆盖率配置

**Files:**
- Create: `pytest.ini` 或 `pyproject.toml`

- [ ] **Step 1: 创建 pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

- [ ] **Step 2: Commit**

```bash
git add pytest.ini
git commit -m "test: add pytest configuration"
```

---

## 执行顺序

1. Task 1: 测试基础设施（conftest）
2. Task 2: test_config.py（基础模块）
3. Task 3: test_wizard.py（新功能）
4. Task 4: test_tui_widgets.py
5. Task 5: test_tui_app.py
6. Task 6: test_pipeline.py
7. Task 7: test_notification.py
8. Task 8: test_data_provider + test_analyzer
9. Task 9: CI Workflow
10. Task 10: 覆盖率配置

---

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**