# open-daily-stock

A 股/港股/美股自选股智能分析系统，**本地 PC 端 TUI + GUI 双模式应用**，你的数据只存在你的电脑里。

## 项目简介

open-daily-stock 是一款面向个人投资者的本地股票分析工具，集成行情追踪、AI 分析、持仓管理、K线回放、机构追踪和策略回测。基于 AkShare + YFinance 免费数据源，支持企业微信、飞书、Telegram 多渠道推送通知。开源免费，本地优先 — 对比雪球/同花顺的云端模式，真正保护你的数据隐私。

## 核心功能

| 功能 | 说明 |
|------|------|
| :chart_with_upwards_trend: **TUI + GUI 双模式** | Textual 终端界面 / Flet 图形界面，功能完全对等 |
| :phone: **三市行情** | A股(akshare)/港股/美股(yfinance)，30s 自动轮询 |
| :robot: **AI 智能分析** | Gemini + OpenAI fallback，决策仪表盘输出 |
| :bell: **多渠道通知** | 企业微信/飞书/Telegram/邮件/Discord |
| :bank: **持仓管理** | 成本盈亏自动计算，实时收益率展示 |
| :chart: **K线回放** | mplfinance 蜡烛图，MA5/MA10/MA20 |
| :mag: **机构追踪** | 大股东增减持、机构调研、龙虎榜 |
| :arrows_counterclockwise: **策略回测** | MA 交叉策略，收益率/最大回撤/夏普比率 |
| :arrow_down: **一键安装** | PyInstaller 打包，下载即用，自动更新 |

## 竞品对比 (2026-05-10 全量调研)

基于 GitHub API 搜索 25+ 同类项目，覆盖 6 个赛道。详见 [competitive-analysis.md](docs/superpowers/plans/2026-05-10-competitive-analysis.md)。

### 核心竞品矩阵

| 产品 | Stars | 部署 | UI | AI 模式 | 策略系统 | 画线 | 机构 | 模拟 |
|------|:-----:|------|------|----------|:--------:|:----:|:----:|:----:|
| **open-daily-stock** | — | **PyInstaller 双击** | **TUI+GUI 双模** | LLM 决策 | MA 交叉 | ✅ | ✅ | ✅ |
| [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | 34.9K | GH Actions/Fork | Web (Streamlit) | 8+ LLM 多模型 | 11 种 YAML | ❌ | ❌ | ❌ |
| [vnpy](https://github.com/vnpy/vnpy) | 40.3K | pip install | Qt GUI | ML 因子 | CTA/套利/做市 | ❌ | ❌ | ✅ |
| [freqtrade](https://github.com/freqtrade/freqtrade) | 50.0K | Docker | Web (React) | FreqAI ML | 完整回测+超参优化 | ❌ | ❌ | ✅ |
| [crewai_stock](https://github.com/liangdabiao/crewai_stock_analysis_system) | 163 | pip | Web (Flask) | CrewAI 多Agent | ❌ | ❌ | ❌ | ❌ |
| [AI-Kline](https://github.com/QuantMLResearch/AI-Kline) | 325 | CLI | CMD+Web+MCP | LSTM+LLM | ❌ | ❌ | ❌ | ❌ |
| [llm-stock-team-analyzer](https://github.com/jason8745/llm-stock-team-analyzer) | 33 | Docker | CLI | LangGraph 4-Agent | ❌ | ❌ | ❌ | ❌ |
| [QuantScope](https://github.com/Kai-dev7/QuantScope) | 22 | Docker | Streamlit+Next.js | Multi-Agent+Quality Gates | ❌ | ❌ | ❌ | ❌ |
| [AlphaAnalyst](https://github.com/kbhujbal/AlphaAnalyst-open-source-autonomous-equity-research-agent) | 26 | Docker | FastAPI+Next.js | DCF+Peer+RAG | ❌ | ❌ | ❌ | ❌ |
| 雪球/同花顺 | — | 云端 | 移动+Web | 基础 | ❌ | ✅ | ✅ | ❌ |
| TradingView | — | 云端 | Web | ❌ | Pine Script | ✅ | ❌ | ✅ |

### open-daily-stock 独占优势 (护城河)

| 独有能力 | 说明 | 竞品盲区 |
|----------|------|----------|
| **TUI+GUI 双模式** | 同一后端，终端/图形界面自由切换 | 竞品均为单一 UI 模式 |
| **PyInstaller 双击安装** | 非开发者可用的安装方式 | 竞品需 pip/Docker/GitHub Actions |
| **机构追踪 + 龙虎榜** | 大股东增减持、机构调研、龙虎榜 | A 股深度功能全部缺失 |
| **画线工具** | K 线图斐波那契回撤 + 支撑阻力位 | 仅 TradingView 有，开源项目全无 |
| **模拟交易** | 100 万虚拟账户 | vnpy/freqtrade 有但面向实盘 |
| **5 渠道通知** | 企微/飞书/Telegram/邮件/Discord | 竞品最多 2 个 |

### AI Agent 赛道对比

| 维度 | open-daily-stock | crewai_stock | llm-stock-team-analyzer | QuantScope |
|------|:---:|:---:|:---:|:---:|
| Agent 框架 | 直接 API 调用 | CrewAI | LangGraph | 自研 adapter |
| Agent 数量 | 1 | 多 (Crew) | 4 (Analyst×3+Trader) | 多 + Quality Gates |
| Agent 反思 | ❌ | ❌ | ✅ Reflection 节点 | ❌ |
| MCP 协议 | ✅ stdio bridge | ❌ | ❌ | ✅ |
| 流式输出 | ✅ | ❌ | ❌ | ❌ |
| RAG | ❌ | ❌ | ❌ | ✅ pgvector |
| 策略 DSL | ❌ | ❌ | ❌ | ❌ |

**定位**: open-daily-stock = 桌面体验最佳的 AI 股票分析工具；daily_stock_analysis = Web 端功能最全的 AI 股票分析平台

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
# 或直接双击打包后的程序
```

### TUI 模式（终端用户/开发者）

```bash
python main.py --tui
```

**快捷键**

| 快捷键 | 功能 |
|--------|------|
| `1-5` / `Tab` | 切换模块 |
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
┌───────────────────────────────────────────────────────┐
│  用户启动 main.py                                      │
│  ↓                                                     │
│  主进程自动 fork DataService (后端守护进程)             │
│  ↓ ↓                                                   │
│  TUI 子进程        GUI 子进程                           │
│  (终端界面)        (Flet 图形界面)                      │
│      ↓                ↓                                │
│  stdio JSON 通信    stdio JSON 通信                     │
│      ↓                ↓                                │
│  ←─── DataService (子进程守护, 19 actions) ───→         │
│       ├── 行情拉取 (AkShare/YFinance)                   │
│       ├── AI 分析 (Gemini/OpenAI)                      │
│       ├── 搜索 (Bocha/Tavily/SerpAPI)                   │
│       ├── 持仓管理 (Portfolio)                          │
│       ├── K线图表 (mplfinance)                          │
│       ├── 机构追踪 (Institutional)                      │
│       ├── 策略回测 (Backtester)                         │
│       └── SQLite 持久化                                 │
└───────────────────────────────────────────────────────┘
```

**进程关系：**
- `main.py` 是唯一入口，自动管理后端进程
- TUI/GUI 作为客户端，通过 stdio 与 DataService 通信
- DataService 后端定时拉取数据，主动推送给客户端

## 下载可执行文件

每次打 tag 自动构建三个平台 Release：

- **Linux**: `open-daily-stock`
- **macOS**: `open-daily-stock-macos`
- **Windows**: `open-daily-stock.exe`
- **GUI 版本**: `open-daily-stock-gui-*`（各平台）

下载地址：https://github.com/mbpz/open-daily-stock/releases

## 项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口（TUI/GUI 自动选择）
├── src/
│   ├── data_service.py  # 后端守护进程
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── portfolio.py     # 持仓成本管理
│   ├── charts.py        # K线图表生成
│   ├── institutional.py # 机构动向追踪
│   ├── backtester.py    # 回测引擎
│   ├── notification.py  # 通知推送
│   ├── update_service.py # 自动更新
│   ├── notify/          # 通知渠道模块
│   │   ├── channels/    # wechat/feishu/telegram/email/discord
│   │   ├── formatters.py
│   │   └── dispatcher.py
│   └── search_pkg/      # 搜索模块
│       ├── base.py / bocha.py / tavily.py / serpapi.py
│       └── manager.py
├── tui/                 # TUI 界面（Textual）
├── gui/                 # GUI 界面（Flet）
│   └── pages/          # Markets/Analyze/Tasks/Config/Logs/Kline
├── data_provider/       # 数据源适配器
└── .github/workflows/   # 构建流程
```

## 配置文件

首次启动会引导用户配置，配置保存在 `config.json`：

```json
{
  "stocks": ["600519", "000001"],
  "apis": {
    "gemini_key": "xxx",
    "deepseek_key": "xxx"
  },
  "notifications": {
    "wecom_webhook": "xxx",
    "feishu_webhook": "xxx"
  },
  "refresh_interval": 30
}
```

## 技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API |
| 数据库 | SQLite + SQLAlchemy ORM |
| 进程通信 | stdio JSON |
| 图表 | mplfinance (K线) |
| 打包 | PyInstaller |

## 文档

- [ROADMAP.md](ROADMAP.md) — 功能规划
- [DESIGN.md](DESIGN.md) — 架构设计
- [docs/COMPETITOR_ANALYSIS.md](docs/COMPETITOR_ANALYSIS.md) — 竞品对比分析
- [docs/adr/](docs/adr/) — 架构决策记录

## License

MIT