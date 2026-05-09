# open-daily-stock

A 股/港股/美股自选股智能分析系统，**本地 PC 端 TUI + GUI 双模式应用**。

## 功能特性

- **TUI 界面** — 终端交互，行情 30s 自动轮询
- **GUI 界面** — Flet 图形界面，点击操作，无需终端
- **双模式并行** — TUI 和 GUI 功能完全对等，用户可选
- **多数据源** — AkShare（免费 A 股）、YFinance（港美股）
- **AI 分析** — Google Gemini / OpenAI 兼容 API（DeepSeek/通义等）
- **多渠道推送** — 企业微信、飞书、Telegram、邮件、Discord
- **持仓管理** — 成本盈亏自动计算，收益率实时展示
- **K线回放** — 历史行情蜡烛图，支持 MA5/MA10/MA20
- **机构追踪** — 大股东增减持、机构调研、龙虎榜
- **简易回测** — 日线级 MA 交叉策略回测，收益率/最大回撤/夏普比率
- **一键安装** — PyInstaller 打包，用户下载即用
- **自动更新** — GitHub Releases 检查，GUI 一键升级

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

## 文档

- [ROADMAP.md](ROADMAP.md) — 功能规划
- [DESIGN.md](DESIGN.md) — 架构设计

## License

MIT