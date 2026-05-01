# open-daily-stock 测试策略设计

## 目标

为 open-daily-stock 设计全面的 TUI 测试方案，覆盖所有模块（80%+ 覆盖率）。

## 测试工具栈

| 工具 | 用途 |
|------|------|
| pytest + pytest-asyncio | 测试运行框架 |
| textual (app.run_test()) | TUI 组件交互测试 |
| pytest-mock | Mock 网络/API 调用 |
| VCR.py | 真实 API 录制/回放 |
| pytest-vcr | VCR pytest 集成 |

## 测试目录结构

```
tests/
├── conftest.py                    # 共享 fixtures
├── test_config.py                 # Config 单例、save_to_env、is_first_time_setup
├── test_wizard.py                 # WizardView 首次启动引导
├── test_tui_widgets.py             # MarketsView, TasksView, AnalyzeView, ConfigView, LogsView
├── test_tui_app.py                # TUIApp 路由、轮询、视图切换
├── test_pipeline.py               # StockAnalysisPipeline 核心流程
├── test_notification.py            # NotificationService Webhook 格式验证
├── test_data_provider/
│   ├── conftest.py               # 数据提供器 shared fixtures
│   ├── test_efinance_fetcher.py  # EfinanceFetcher（VCR 录制）
│   ├── test_akshare_fetcher.py   # AkshareFetcher
│   └── test_wrapper.py           # DataProviderWrapper
├── test_analyzer.py               # AI Analyzer（LUI 集成）
└── fixtures/                      # VCR cassettes, mock data
    ├── cassettes/                 # VCR 录制文件
    └── mock_data/                 # 测试用 mock JSON
```

## 测试分层

### 1. 核心逻辑测试 (test_config.py)

```python
def test_is_first_time_setup_no_env():
    """无 .env 时返回 True"""
    # 删除 .env，调用 is_first_time_setup()

def test_is_first_time_setup_no_api_key():
    """无 API Key 时返回 True"""
    # .env 存在但无 openai_api_key

def test_save_to_env():
    """保存配置到 .env"""
    # 写入配置，验证文件内容

def test_refresh_from_updates():
    """刷新配置属性"""
    # 调用 refresh_from_updates，验证属性更新
```

### 2. TUI Wizard 测试 (test_wizard.py)

```python
async def test_wizard_step1_display():
    """步骤1显示正确"""
    app = TUIApp()
    app._show_wizard = True
    async with app.run_test() as pilot:
        # 验证显示 "步骤 1/3: 配置 API Key"

async def test_wizard_navigate_fields():
    """↑↓ 导航字段"""
    # 按下键，验证选中项变化

async def test_wizard_edit_field():
    """Enter 编辑字段"""
    # 按 Enter，输入值，验证更新

async def test_wizard_complete():
    """完成引导"""
    # 填写所有必填项，按 Enter 完成，验证进入 Markets

async def test_wizard_skip():
    """跳过引导"""
    # 在步骤3按 Esc，验证跳过并进入 Markets
```

### 3. TUI Widgets 测试 (test_tui_widgets.py)

```python
async def test_markets_display_empty():
    """无数据时显示空状态"""

async def test_markets_display_data():
    """有数据时显示行情"""

async def test_config_display_fields():
    """ConfigView 显示所有字段"""

async def test_config_edit_and_save():
    """编辑并保存配置"""

async def test_tasks_view():
    """TasksView 显示任务列表"""

async def test_logs_view():
    """LogsView 读取日志文件"""
```

### 4. Pipeline 测试 (test_pipeline.py)

```python
async def test_pipeline_fetch_data():
    """Pipeline 获取数据"""

async def test_pipeline_analyze():
    """Pipeline 执行分析"""

async def test_pipeline_notify():
    """Pipeline 发送通知"""
```

### 5. Data Provider 测试 (VCR 录制)

```python
def test_efinance_fetch_success(httpserver):
    """EfinanceFetcher 成功获取数据"""
    # 使用 VCR 录制真实 API 响应

def test_akshare_fetch_retry():
    """AkshareFetcher 重试逻辑"""
```

### 6. Notification 测试 (test_notification.py)

```python
def test_wechat_webhook_format():
    """企业微信 Webhook 格式验证"""

def test_feishu_webhook_format():
    """飞书 Webhook 格式验证"""

def test_notification_skip_when_disabled():
    """未配置时跳过通知"""
```

### 7. Analyzer 测试 (test_analyzer.py)

```python
async def test_analyzer_local_llm():
    """使用本地 LLM（Claude Code）分析"""
    # 需要 CLAUDE_API_KEY 环境变量

async def test_analyzer_fallback():
    """LLM 失败时 fallback"""
```

## CI 策略

### GitHub Actions Workflow

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt
        pip install pytest pytest-asyncio textual pytest-mock vcrpy

      - name: Run unit tests (mock network)
        run: pytest tests/ -v --mock-network

      - name: Run with real API (if secrets available)
        if: env.CLAUDE_API_KEY != ''
        run: pytest tests/test_analyzer.py -v

  notify-test:
    needs: test
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - name: Send test notification
        env:
          WECHAT_WEBHOOK_URL: ${{ secrets.WECHAT_WEBHOOK_URL }}
        run: pytest tests/test_notification.py::test_send_real_notification -v
```

### CI 环境变量

```bash
# .env.test（不提交到 git）
CLAUDE_API_KEY=sk-xxx
OPENAI_API_KEY=eyJxxx
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/...
```

## 本地测试命令

```bash
# 运行所有测试
pytest tests/ -v

# 运行 TUI 测试
pytest tests/test_wizard.py tests/test_tui_widgets.py -v

# 使用真实 API 运行（本地）
export CLAUDE_API_KEY=sk-xxx
pytest tests/test_analyzer.py -v

# 录制新的 VCR cassettes
pytest tests/test_data_provider/ --record-mode=new_episodes
```

## 测试覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| src/config.py | 90%+ |
| tui/widgets/wizard.py | 90%+ |
| tui/app.py | 80%+ |
| src/core/pipeline.py | 80%+ |
| src/notification.py | 70%+ |
| data_provider/ | 60%+ |

## 测试数据管理

### .env.test 文件

```bash
# tests/.env.test（通过 .gitignore 排除）
CLAUDE_API_KEY=sk-test
OPENAI_API_KEY=eyJtest
OPENAI_BASE_URL=https://api.minimax.chat/v1
OPENAI_MODEL=abab6-chat
STOCK_LIST=000001,600519
WECHAT_WEBHOOK_URL=https://test.webhook.com
```

### VCR Cassettes

```bash
tests/fixtures/cassettes/
├── efinance_fetcher_success.yaml
├── akshare_fetcher_market_data.yaml
└── yfinance_fetcher_hk.yaml
```

## 执行顺序

1. **test_config.py** — Config 是基础，所有模块依赖它
2. **test_wizard.py** — 新功能优先，用户体验关键
3. **test_tui_widgets.py** — 其他 TUI 模块
4. **test_tui_app.py** — App 集成
5. **test_pipeline.py** — 核心业务逻辑
6. **test_data_provider/** — 数据层
7. **test_notification.py** — 通知服务
8. **test_analyzer.py** — AI 分析器

## 替代方案（未选择）

- **方案 2（简化策略）**：减少测试数量，但无法保证 80%+ 覆盖率
- **方案 3（仅本地测试）**：CI 不运行完整测试，发布风险高

## 优先级

P0 — 必须实现，TUI 应用稳定性关键