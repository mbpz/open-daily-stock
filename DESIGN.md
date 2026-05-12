# open-daily-stock 设计文档

---

## 一、项目定位

**本地 PC 端 GUI 应用**。用户下载打包好的 DMG，双击运行即可使用所有功能，无需安装 Python、无需配置服务端。

**核心场景：** 用户在图形界面查看自选股行情、手动触发股票分析、配置通知渠道、追踪持仓成本、K线图表、运行策略回测。

**核心差异化：**
1. LLM 决策仪表盘（非简单技术指标）
2. 多渠道通知（企业微信、飞书、Telegram 等国内主流）
3. 本地优先（无需服务器、无需安装 Python）
4. 持仓成本管理 + K线回放
5. 简易日线级回测引擎

---

## 二、设计原则

### 2.1 极简依赖
- 只依赖 Python 标准库 + PyInstaller
- 数据来源：AkShare/Efinance（免费 A 股数据）、YFinance（港美股）
- AI 分析：用户自己的 API Key（Gemini/OpenAI 兼容）

### 2.2 本地优先
- 所有数据本地存储（SQLite）
- 不需要任何服务端
- 网络只用于：拉取行情数据、拉取 AI 分析结果、推送通知到用户配置的 Webhook

### 2.3 界面与后端分离
- GUI 只负责交互（展示、输入、导航）
- DataService 后端负责数据拉取、缓存、分析
- 业务逻辑在 src/（GUI 通过 stdio JSON 调用）

### 2.4 单一职责
- 界面层只负责交互（展示、输入、导航）
- DataService 后端负责数据拉取、缓存、推送
- 业务逻辑在 src/（可被 main.py CLI 复用）

---

## 三、架构设计

### 3.1 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│           GUI 层（Flet）                                    │
│  StockApp (NavigationRail 6 页)                             │
└──────────────────────────┬──────────────────────────────────┘
                           │    stdio JSON (ServiceClient)
┌──────────────────────────┴──────────────────────────────────┐
│           DataService (后端守护进程)                         │
│  - 数据拉取 (AkShare/YFinance/Efinance)                     │
│  - 缓存管理 (SQLite + MarketDataCache)                      │
│  - 定时推送 (30s)                                           │
│  - AI 分析 (Gemini/DeepSeek/多 Agent 流式)                   │
│  - 持仓管理 (Portfolio)                                     │
│  - K线图表 (Charts)                                        │
│  - 机构追踪 (Institutional)                                 │
│  - 策略回测 (Backtester)                                    │
│  - RAG 知识库 (FTS5)                                        │
│  - MCP Server (JSON-RPC 2.0 stdio)                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│           数据层                                             │
│  data_provider/ (插件架构) · SQLite                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 进程模型

```
main.py (GUI 入口)
    ↓
fork() → DataService 子进程
    ↓
    ├── stdin: 接收客户端请求 (JSON)
    ├── stdout: 发送响应/推送数据 (JSON)
    └── SQLite: 数据持久化

ServiceClient (GUI 子进程)
    ↓
    └── stdin/stdout 连接 DataService
```

**进程启动流程：**
1. 用户运行 `main.py`
2. main.py 启动 Flet GUI (StockApp)
3. StockApp.__init__ 中创建 ServiceClient，自动 fork DataService 子进程
4. GUI 作为客户端通过 stdio JSON 与 DataService 通信

### 3.3 通信协议

**请求格式（客户端 → DataService）：**
```json
// 行情
{"action": "get_markets"}
{"action": "refresh_data"}
// AI 分析
{"action": "analyze", "code": "600519"}
{"action": "deep_analyze", "code": "600519", "agents": ["technical", "fundamental", "news"]}
// 历史数据 & 图表
{"action": "get_history", "code": "600519"}
{"action": "get_kline_data", "code": "600519", "days": 60}
// 搜索
{"action": "search_news", "code": "600519"}
// 持仓
{"action": "add_position", "code": "600519", "name": "茅台", "shares": 100, "buy_price": 1800.0}
{"action": "get_positions"}
// 机构追踪
{"action": "get_institutional", "code": "600519"}
{"action": "get_dragon_board"}
// 回测
{"action": "run_backtest", "code": "600519", "days": 120, "initial_capital": 100000}
// 任务管理
{"action": "get_tasks"}
{"action": "cancel_task", "task_id": "xxx"}
// RAG 知识库
{"action": "rag_search", "code": "600519", "query": "xxx"}
// 因子分析
{"action": "get_factor_value", "code": "600519", "factor": "pe_ratio"}
{"action": "analyze_factor_ic", "factor": "pe_ratio"}
// Agentic Research
{"action": "research", "code": "600519", "topic": "投资价值分析"}
// 配置
{"action": "get_config"}
{"action": "update_config", "data": {...}}
```

**响应格式（DataService → 客户端）：**
```json
{"status": "ok", "data": {...}}
{"status": "error", "message": "..."}
{"type": "push", "data": {"markets": [...], "timestamp": "..."}}
```

---

## 四、数据流向

### 4.1 客户端启动
```
GUI 启动 (StockApp.__init__)
    ↓
ServiceClient 初始化 → fork DataService 子进程
    ↓
发送 hello 请求
    ↓
DataService 返回版本信息
    ↓
GUI 展示主界面，加载 markets 数据
```

### 4.2 定时刷新
```
DataService 定时器 (30s)
    ↓
拉取 AkShare/YFinance/Efinance 数据
    ↓
更新 SQLite 缓存
    ↓
主动推送数据到 GUI
    ↓
GUI 更新界面显示
```

### 4.3 手动刷新
```
用户点击刷新按钮
    ↓
GUI 发送 refresh 请求
    ↓
DataService 立即拉取数据
    ↓
推送新数据到 GUI
```

### 4.4 AI 分析
```
用户输入股票代码，点击分析
    ↓
GUI 发送 analyze/deep_analyze 请求
    ↓
DataService 执行分析 Pipeline（单 Agent 或多 Agent）
    ↓
流式返回分析结果 / 完成后推送通知
    ↓
GUI 展示分析结果
```

---

## 五、模块设计

### 5.1 main.py（唯一入口）

```
职责：
- 配置日志
- 启动 Flet GUI (StockApp)
- 处理 --check-update 参数
```

### 5.2 DataService（后端守护进程）

```
职责：
- 数据拉取（AkShare/YFinance/Efinance）
- SQLite 缓存管理
- 定时推送数据
- AI 分析执行（单 Agent / 多 Agent / 流式）
- RAG 知识库 (FTS5)
- 配置管理
- 持仓管理 (portfolio)
- 新闻搜索 (search_news)
- K线数据 (kline_data)
- 机构追踪 (institutional)
- 策略回测 (backtest)
- 因子分析 (factor_engine)
- Agentic Research (research_agent)
- MCP Server (stdio JSON-RPC 2.0)

接口：
- stdio JSON 通信（主接口）
- WebSocket 服务器（内部 IPC，port 9876）
```

### 5.3 ServiceClient（GUI 通信层）

```
职责：
- fork 并管理 DataService 子进程
- stdio JSON 请求/响应封装
- 方法：hello, get_markets, refresh, analyze, deep_analyze, get_config, update_config, quit
```

### 5.4 GUI 页面（gui/pages/）

```
pages/ (14 个页面模块)
├── markets.py    # 自选股行情列表
├── analyze.py    # AI 分析触发页
├── tasks.py      # 分析任务历史
├── config.py     # 配置管理
├── logs.py       # 日志查看
├── chart.py      # K线图表 + 画线工具
├── strategies.py # 策略管理（回测/模拟交易）
├── notifications.py # 通知中心
├── command_palette.py # Ctrl+K 命令面板
├── screener.py   # 股票筛选器
└── financials.py # 财务报表
```

---

## 六、配置文件

### 6.1 配置文件位置

`~/.open-daily-stock/config.json` 或 `config.json`（工作目录）

### 6.2 配置结构

```json
{
  "stocks": ["600519", "000001"],
  "apis": {
    "gemini_key": "xxx",
    "deepseek_key": "xxx"
  },
  "notifications": {
    "wecom_webhook": "xxx",
    "feishu_webhook": "xxx",
    "telegram_bot_token": "xxx",
    "smtp_email": "xxx"
  },
  "refresh_interval": 30
}
```

---

## 七、设计思想

### 7.1 单一入口

`main.py` 是唯一入口，直接启动 Flet GUI。ServiceClient 在 StockApp 初始化时自动启动 DataService 子进程。

### 7.2 界面与后端分离

GUI 和 DataService 共享同一个后端，数据完全一致。界面层只负责交互，不处理业务逻辑。

### 7.3 缓存优先

DataService 维护本地 SQLite 缓存 + MarketDataCache，即使数据源不可用也能展示历史数据。网络降级时自动切换。

### 7.4 主动推送

DataService 定时拉取数据并主动推送到 GUI，GUI 无需频繁轮询。

### 7.5 插件架构

数据源通过 `ProviderRegistry` 插件系统管理，支持按优先级自动故障切换。外部插件可动态加载。

---

## 八、DataService Action 清单（40+ actions）

| Action | 功能 | 来源 |
|--------|------|------|
| `hello` | 健康检查 | 原有 |
| `get_markets` | 获取行情数据 | 原有 |
| `refresh` | 刷新数据 | 原有 |
| `get_history` | 获取历史 K 线 | P0-1 |
| `get_kline_data` | K 线数据 | P1-5 |
| `analyze` | AI 分析（流式） | P5-1 |
| `deep_analyze` | 多 Agent 分析 | P5-5 |
| `analyze_stream` | 流式分析 | P5-1 |
| `search_news` | 搜索新闻 | P0-1 |
| `get_tasks` / `get_task` / `cancel_task` | 任务管理 | P0-1 |
| `add_position` / `remove_position` / `update_position` / `get_positions` | 持仓管理 | P1-4 |
| `get_institutional` / `get_dragon_board` | 机构追踪 | P1-6 |
| `run_backtest` | 策略回测 | P1-7 |
| `sim_buy` / `sim_sell` / `sim_summary` / `sim_history` / `sim_reset` | 模拟交易 | P4-2 |
| `get_financials` / `get_key_metrics` | 财务报表 | P4-3 |
| `rag_search` / `search_knowledge` | FTS5 知识库 | P5-6 |
| `research` | Agentic Research | P5-9 |
| `get_factor_value` / `analyze_factor_ic` / `get_factor_rankings` | 因子分析 | P5-10 |
| `get_alerts` / `save_alert` / `delete_alert` / `toggle_alert` | 价格告警 | P0-2 |
| `list_providers` | 数据源列表 | — |
| `get_config` / `update_config` | 配置管理 | — |
| `get_theme` / `set_theme` | 主题切换 | P2-2 |
| `get_languages` / `set_language` | 多语言 | P2-3 |
| `export_strategy` / `import_strategy` / `list_strategies` / `delete_strategy` | 策略管理 | — |
| `quit` | 退出服务 | 原有 |

---

## 九、非目标（Out of Scope）

- 不支持 Web UI
- 不支持远程服务器管理
- 不实现 tick 级 K 线（仅日线级别）
- 不支持高频交易策略回测
- 不支持实盘交易（法律风险）