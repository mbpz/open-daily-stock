# open-daily-stock

**本地桌面 AI 股票分析工具** — 双击即用，AI 深度分析，机构追踪，策略回测。

## 核心差异化

| 能力 | open-daily-stock | 雪球/同花顺 | TradingView |
|------|:---:|:---:|:---:|
| **安装方式** | PyInstaller 双击即用 | 云端 | Web |
| **本地数据** | 所有数据存在本地 | 云端 | 云端 |
| **机构追踪** | 大股东/调研/龙虎榜 | ✅ | ❌ |
| **画线工具** | 斐波那契 + 支撑阻力 | ✅ | ✅ |
| **模拟交易** | 100万虚拟账户 | ❌ | ✅ |
| **通知渠道** | 企微/飞书/TG/邮件/Discord | 1-2个 | 1-2个 |
| **Command Palette** | Ctrl+K 模糊搜索 | ❌ | ❌ |
| **通知中心** | 本地 Toast + 历史 | ✅ | ✅ |

## Quick Install

```bash
# macOS
brew install mbpz/tap/open-daily-stock

# Windows
winget install mbpz.open-daily-stock

# Any platform (pip)
pip install open-daily-stock
```

## One-Click Cloud Deployment (GitHub Actions)

No local installation needed — fork and run in the cloud:

1. **Fork** this repository
2. Go to **Settings → Secrets and variables → Actions** and add:
   - `DEEPSEEK_API_KEY` — your DeepSeek API key
   - `STOCK_LIST` — comma-separated codes, e.g. `600519,000001,300750`
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (optional, for notifications)
3. Enable **Actions** in your fork
4. The workflow runs automatically at 15:30 CST (after market close) on weekdays
5. Results sent via Telegram or saved as workflow artifacts

→ See [.github/workflows/daily-analysis.yml](.github/workflows/daily-analysis.yml)

## Quick Start (Desktop)

### GUI 模式

```bash
python main.py
```

**快捷键**

| 快捷键 | 功能 |
|--------|------|
| `1-5` / `Tab` | 切换模块 |
| `Ctrl+K` | Command Palette 命令面板 |
| `r` | 手动刷新行情 |
| `q` | 退出 |

**六个模块**

| 快捷键 | 模块 | 说明 |
|--------|------|------|
| `1` | 图表 | K线 + 画线工具 |
| `2` | 行情 | 自选股实时行情 |
| `3` | 分析 | 手动触发 AI 分析 |
| `4` | 任务 | 分析任务历史 |
| `5` | 配置 | 配置管理 |
| `6` | 日志 | 日志查看 |

## English

**open-daily-stock** is a local-first desktop AI stock analysis tool. Double-click to run — no Python, no server, no Docker.

- 📊 Real-time A-Share / HK / US stock quotes (AkShare, YFinance, Efinance)
- 🤖 AI analysis with multi-agent collaboration (DeepSeek + streaming)
- 📈 8 built-in trading strategies with backtesting
- 🔔 5 notification channels (WeCom, Feishu, Telegram, Email, Discord)
- 🏦 Portfolio tracking, institutional flows, simulated trading
- 🧩 Plugin architecture (13 built-in plugins, 4 domains)
- ⚡ Optional Rust acceleration for backtest engine (5-8x speedup)

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  用户启动 main.py → Flet GUI                                │
│  ↓                                                           │
│  StockApp (NavigationRail 6 页)                              │
│             ↓                                                │
│  ServiceClient (子进程 stdio)                              │
│             ↓                                                │
│  ←──────── DataService (子进程守护, 40+ actions) ────→     │
│       ├── 行情拉取 (AkShare/YFinance/Efinance)               │
│       ├── AI 分析 (Gemini + OpenAI, 流式输出)                │
│       ├── 多 Agent 协同 (技术/基本面/新闻+合成)               │
│       ├── RAG 知识库 (FTS5 全文检索)                         │
│       ├── 搜索 (Bocha/Tavily/SerpAPI)                        │
│       ├── 持仓管理 (Portfolio)                               │
│       ├── K线图表 (mplfinance)                               │
│       ├── 机构追踪 (Institutional)                          │
│       ├── 策略回测 (Backtester)                              │
│       ├── MCP Server (stdio JSON-RPC 2.0)                   │
│       └── SQLite 持久化                                      │
└─────────────────────────────────────────────────────────────┘
```

**进程关系：**
- `main.py` 是唯一入口，启动 Flet GUI
- GUI 通过 `ServiceClient`（子进程 stdio JSON）与 DataService 通信
- DataService 作为子进程守护运行，处理所有业务逻辑

## 项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口（GUI）
├── src/
│   ├── data_service.py  # 后端守护进程（40+ actions）
│   ├── analyzer.py      # AI 分析器（流式）
│   ├── agents/         # 多 Agent 协同 (P5-5)
│   │   ├── orchestrator.py
│   │   ├── technical_agent.py
│   │   ├── fundamental_agent.py
│   │   ├── news_agent.py
│   │   └── synthesizer_agent.py
│   │   └── research_agent.py  # Agentic Research (P5-9)
│   ├── factor_engine.py # 因子分析引擎 (P5-10)
│   ├── rag_store.py    # FTS5 知识库 (P5-6)
│   ├── mcp_tools.py    # MCP Tool 定义 (P5-2)
│   ├── mcp_server.py   # MCP stdio Server (P5-2)
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── portfolio.py     # 持仓成本管理
│   ├── charts.py        # K线图表生成
│   ├── institutional.py # 机构动向追踪
│   ├── backtester.py    # 回测引擎
│   ├── notification_center.py # 通知中心 (P5-8)
│   └── notify/channels/ # 通知渠道 wechat/feishu/telegram/email/discord
├── data_provider/       # 多源数据获取（插件架构）
│   ├── akshare_fetcher.py
│   ├── yfinance_fetcher.py
│   ├── efinance_fetcher.py
│   ├── baostock_fetcher.py
│   └── plugin.py        # ProviderRegistry
├── gui/                 # GUI 界面（Flet）
│   └── pages/         # markets/analyze/tasks/config/logs/chart/strategies/notifications
└── tests/              # 750+ 测试
```

## 功能列表

| 功能 | 说明 |
|------|------|
| :chart_with_upwards_trend: **GUI 桌面** | Flet 图形界面，NavigationRail 导航 |
| :phone: **三市行情** | A股(AkShare/Efinance)/港股/美股(YFinance)，30s 自动轮询 |
| :robot: **AI 智能分析** | 多 Agent 协同 + RAG 知识库 + 流式输出 |
| :bell: **多渠道通知** | 企业微信/飞书/Telegram/邮件/Discord |
| :bank: **持仓管理** | 成本盈亏自动计算，实时收益率展示 |
| :chart: **K线图表** | mplfinance 蜡烛图，MA5/MA10/MA20 |
| :mag: **机构追踪** | 大股东增减持、机构调研、龙虎榜 |
| :arrows_counterclockwise: **策略回测** | MA 交叉策略，收益率/最大回撤/夏普比率 |
| :keyboard: **Command Palette** | Ctrl+K 模糊搜索所有命令 |
| :loud_sound: **通知中心** | 本地 Toast + 通知历史 |
| :link: **MCP Server** | stdio JSON-RPC 2.0，AI Agent 可直接调用 |
| :arrow_down: **一键安装** | PyInstaller 打包，Homebrew/winget 一行命令安装 |
| :bar_chart: **因子分析引擎** | PE/PB/动量/量比/RSI，IC/IR 分析 (P5-10) |
| :microscope: **Agentic Research** | LLM 自主多步研究 (P5-9) |

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance、Efinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API + 多 Agent + 流式 |
| 数据库 | SQLite + SQLAlchemy ORM |
| 进程通信 | stdio JSON |
| 图表 | mplfinance (K线) |
| 打包 | PyInstaller |

## 文档

- [ROADMAP.md](ROADMAP.md) — 功能规划（P0-P7 完整任务列表）
- [DESIGN.md](DESIGN.md) — 架构设计文档

## License

MIT