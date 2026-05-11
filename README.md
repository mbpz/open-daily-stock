# open-daily-stock

**本地桌面 AI 股票分析工具** — TUI + GUI 双模式，30s 自动刷新，AI 深度分析，机构追踪，策略回测。

## 核心差异化

| 能力 | open-daily-stock | 雪球/同花顺 | TradingView |
|------|:---:|:---:|:---:|
| **安装方式** | PyInstaller 双击即用 | 云端 | Web |
| **本地数据** | 所有数据存在本地 | 云端 | 云端 |
| **TUI 终端** | ✅ | ❌ | ❌ |
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

## 快速开始

### GUI 模式（推荐普通用户）

```bash
python main.py --gui
```

### TUI 模式（终端用户/开发者）

```bash
python main.py --tui
```

**快捷键**

| 快捷键 | 功能 |
|--------|------|
| `1-5` / `Tab` | 切换模块 |
| `Ctrl+K` | Command Palette 命令面板 |
| `r` | 手动刷新行情 |
| `q` | 退出 |

**五个模块**

| 快捷键 | 模块 | 说明 |
|--------|------|------|
| `1` | Markets | 自选股实时行情 |
| `2` | Tasks | 分析任务历史 |
| `3` | Analyze | 手动触发分析 |
| `4` | Config | 配置管理 |
| `5` | Logs | 日志查看 |

### 命令行模式

```bash
python main.py                    # 完整分析 + 推送
python main.py --check-update     # 检查更新
python main.py --refresh-data      # 刷新数据
python main.py --dry-run          # 仅获取数据
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  用户启动 main.py                                            │
│  ↓                                                           │
│  ┌─ python main.py --gui ──┐  ┌─ python main.py --tui ──┐  │
│  │   GUI 独立进程            │  │   TUI 独立进程           │  │
│  │   (Flet 图形界面)         │  │   (Textual 终端界面)     │  │
│  │         ↓                 │  │         ↓                │  │
│  │   ServiceClient          │  │   ServiceClient          │  │
│  │   (子进程 stdio)         │  │   (子进程 stdio)         │  │
│  └──────────┬────────────────┘  └──────────┬────────────────┘  │
│             ↓                              ↓                   │
│  ←──────── DataService (子进程守护, 30 actions) ────→         │
│       ├── 行情拉取 (AkShare/YFinance)                        │
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
- `main.py` 是唯一入口，根据 `--gui` / `--tui` 决定启动哪个 UI
- GUI 和 TUI 各自由 `gui/main.py` / `tui/main.py` 直接启动（独立进程）
- 两个 UI 通过 `ServiceClient`（子进程 stdio JSON）与 DataService 通信
- `python main.py` 无参数时：启动 DataService 子进程后执行 CLI 完整分析 + 推送

## 项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口（TUI/GUI 自动选择）
├── src/
│   ├── data_service.py  # 后端守护进程
│   ├── analyzer.py      # AI 分析器
│   ├── agents/         # 多 Agent 协同 (P5-5)
│   │   ├── technical.py
│   │   ├── fundamental.py
│   │   ├── news.py
│   │   └── synthesizer.py
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── portfolio.py     # 持仓成本管理
│   ├── charts.py        # K线图表生成
│   ├── institutional.py # 机构动向追踪
│   ├── backtester.py    # 回测引擎
│   ├── notification.py  # 通知推送
│   ├── rag.py          # RAG 上下文构建 (P5-6)
│   ├── rag_store.py    # FTS5 知识库
│   ├── commands.py      # 命令统一定义 (P5-7)
│   ├── notification_center.py # 通知中心 (P5-8)
│   ├── mcp_tools.py    # MCP Tool 定义
│   ├── mcp_server.py   # MCP stdio Server
│   └── notify/         # 通知渠道模块
│       └── channels/   # wechat/feishu/telegram/email/discord
├── tui/                 # TUI 界面（Textual）
│   └── widgets/        # Markets/Analyze/Tasks/Config/Logs/Kline
├── gui/                 # GUI 界面（Flet）
│   └── pages/         # Markets/Analyze/Tasks/Config/Logs/Kline
├── tests/              # 227+ 测试
└── docs/
    └── superpowers/
        └── specs/      # 设计文档
```

## 功能列表

| 功能 | 说明 |
|------|------|
| :chart_with_upwards_trend: **TUI + GUI 双模式** | Textual 终端界面 / Flet 图形界面，功能完全对等 |
| :phone: **三市行情** | A股(akshare)/港股/美股(yfinance)，30s 自动轮询 |
| :robot: **AI 智能分析** | 多 Agent 协同 + RAG 知识库 + 流式输出 |
| :bell: **多渠道通知** | 企业微信/飞书/Telegram/邮件/Discord |
| :bank: **持仓管理** | 成本盈亏自动计算，实时收益率展示 |
| :chart: **K线回放** | mplfinance 蜡烛图，MA5/MA10/MA20 |
| :mag: **机构追踪** | 大股东增减持、机构调研、龙虎榜 |
| :arrows_counterclockwise: **策略回测** | MA 交叉策略，收益率/最大回撤/夏普比率 |
| :keyboard: **Command Palette** | Ctrl+K 模糊搜索所有命令 |
| :loud_sound: **通知中心** | 本地 Toast + 通知历史 |
| :link: **MCP Server** | stdio JSON-RPC 2.0，AI Agent 可直接调用 |
| :arrow_down: **一键安装** | PyInstaller 打包，下载即用，自动更新 |

## 技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API + 多 Agent |
| 数据库 | SQLite + SQLAlchemy ORM |
| 进程通信 | stdio JSON |
| 图表 | mplfinance (K线) |
| 打包 | PyInstaller |

## 文档

- [ROADMAP.md](ROADMAP.md) — 功能规划（已完成 P0-P5）
- [docs/superpowers/plans/2026-05-10-competitive-analysis.md](docs/superpowers/plans/2026-05-10-competitive-analysis.md) — 竞品对比分析（2026-05-10）

## License

MIT