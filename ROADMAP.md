# open-daily-stock Roadmap

**项目定位：** 本地 PC 端 TUI + GUI 双模式应用，无需服务端，打包后用户安装即可使用所有功能。

---

## 一、TUI/GUI 双模式（核心架构）

| 模式 | 入口 | 说明 |
|------|------|------|
| GUI | `python main.py --gui` | Flet 图形界面，普通用户推荐 |
| TUI | `python main.py --tui` | Textual 终端界面，开发者/技术用户 |

**双模式架构：**

```
main.py (唯一入口)
    ↓
自动 fork DataService (后端守护进程)
    ↓ ↓
TUI 子进程    GUI 子进程
stdio JSON    stdio JSON
    ↓            ↓
←──── DataService (统一后端) ────→
```

---

## 二、已完成功能

### 2.1 行情数据

| 功能 | TUI | GUI |
|------|-----|-----|
| A 股实时行情（AkShare） | ✅ | ✅ |
| 港股/美股行情（YFinance） | ✅ | ✅ |
| 自选股列表管理 | ✅ | ✅ |
| 手动刷新 | ✅ | ✅ |
| 自动轮询（30s 可配置） | ✅ | ✅ |

### 2.2 AI 分析

| 功能 | TUI | GUI |
|------|-----|-----|
| Google Gemini API | ✅ | ✅ |
| OpenAI 兼容 API（DeepSeek/通义等） | ✅ | ✅ |
| 分析结果展示 | ✅ | ✅ |

### 2.3 通知渠道

| 功能 | TUI | GUI |
|------|-----|-----|
| 企业微信 Webhook | ✅ | ✅ |
| 飞书 Webhook | ✅ | ✅ |
| Telegram Bot | ✅ | ✅ |
| 邮件通知（SMTP） | ✅ | ✅ |
| 自定义 Webhook | ✅ | ✅ |

### 2.4 自动更新

| 功能 | 状态 |
|------|------|
| GitHub Releases 检查 | ✅ |
| GUI 状态栏更新按钮 | ✅ |
| CLI --check-update | ✅ |

---

## 三、重构任务（优化架构）

### 高优先级

- [x] **P0-1: DataService Action 扩展** ✅
  - 新增: `analyze` / `get_history` / `search_news` / `get_tasks` / `cancel_task`
  - 当前只有 4 个 action → 扩展至 10+ action
  - 文件: `src/data_service.py`

- [x] **P0-2: notification.py 模块化拆解** ✅
  - 拆分为: `notify/channels/` (wechat/feishu/telegram/email/discord) + `formatters.py` + `dispatcher.py`
  - 文件: `src/notification.py` → `src/notify/`
  - 目标: 单文件 < 800 行 ✓

- [x] **P0-3: search_service.py 模块化** ✅
  - 拆分为: `search_pkg/` (bocha/tavily/serpapi/manager)
  - 文件: `src/search_service.py` → `src/search_pkg/`

### 中优先级

- [x] **P1-1: 数据层增强** ✅
  - `CURRENT_SCHEMA_VERSION = 2` 常量 + `SchemaVersion` ORM model
  - `save_task` / `load_tasks` / `get_task` 任务持久化方法到 DatabaseManager
  - `migrate_analysis_history`：自动添加 task_id 列
  - 10 个测试

- [x] **P1-2: TUI/GUI 代码复用** ✅
  - `src/shared/` 包：style.py / market_status.py / indicators.py
  - Indicators 迁移到 shared 包，charts.py 委托调用
  - `get_market_status()` 支持 A股/港股/美股交易时间判断
  - `format_volume()` / `format_percent()` 等格式化函数统一复用

- [x] **P1-3: 错误恢复增强** ✅
  - `MarketDataCache` TTL 缓存 (A股 1天/港美股 1小时)
  - ThreadPoolExecutor per-request timeout (30s)
  - AI API 429 指数退避 (60s → 300s → 600s)
  - 3次连续429后熔断30分钟
  - 网络降级: live失败 → 缓存数据 + 警告
  - 心跳 watchdog (30s 间隔)
  - 16 个新测试

- [x] **P1-4: 持仓成本管理** ✅
  - `src/portfolio.py` — Position dataclass + 成本盈亏计算
  - DataService actions: add_position / remove_position / update_position / get_positions
  - SQLite positions 表持久化
  - 24 个测试

- [x] **P1-5: K线历史回放** ✅
  - `src/charts.py` — mplfinance 蜡烛图 + MA5/MA10/MA20
  - `gui/pages/kline.py` — Flet K线页面
  - DataService action: get_kline_data
  - 11 个测试

- [x] **P1-6: 机构动向追踪** ✅
  - `src/institutional.py` — 大股东增减持 + 机构调研 + 龙虎榜
  - DataService actions: get_institutional / get_dragon_board
  - akshare 优先 + 搜索回退
  - 9 个测试

- [x] **P1-7: 简易回测引擎** ✅
  - `src/backtester.py` — MA5/MA20 交叉策略回测
  - 指标: total_return / max_drawdown / sharpe_ratio / win_rate
  - DataService action: run_backtest
  - 18 个测试

### 低优先级

- [x] **P2-1: 快捷键配置化** ✅
  - 嵌套 section (global/markets/analysis/tasks)，向后兼容旧平面格式，15 tests

- [ ] **P2-2: 主题切换**（深/浅色）

- [ ] **P2-3: 多语言扩展**（日语、韩语）

### 功能增强 P3（竞品分析驱动）

基于技术架构、产品功能、用户体验、市场策略4维度竞品分析。

- [x] **P3-1: 扩展技术指标** ✅ — RSI/MACD/Bollinger Bands/KDJ/WR/OBV（charts.py 扩展，18 tests）
- [x] **P3-2: 股票选股器** ✅ — AkShare 筛选器 + GUI/TUI 页面（31 tests）
- [x] **P3-3: Alert 配置 UI** ✅ — Config 页面 Alerts tab + TUI alerts mode
- [x] **P3-4: AI Verdict Badge** ✅ — 看涨/看跌徽章 + 情感评分条 + 催化剂/风险分区
- [x] **P3-5: 实时更新闪烁** ✅ — 价格变化 cell 黄色闪烁 300ms
- [x] **P3-6: 成交量单位格式化** ✅ — A股/港股"万"，美股"M/K"
- [x] **P3-7: 市场状态指示器** ✅ — A股/港股/美股 交易中/盘前/休市 徽章

### 架构增强 P3

- [x] **P3-8: 统一存储层** ✅ — 全部迁移到 storage.py SQLAlchemy ORM（29 tests）
- [x] **P3-9: WebSocket IPC 模式** ✅ — DataService 支持 `--ws-server`，websockets 库，7 tests
- [x] **P3-10: per-request 超时保护** ✅ — handler thread pool + 30s timeout（P1-3 完成）
- [x] **P3-11: ADR 文档** ✅ — docs/adr/ 目录，4 篇架构决策记录

### 高级功能 P4

- [x] **P4-1: 画线工具** ✅ — K线图支持斐波那契回撤 + 支撑压力位，23 tests
- [x] **P4-2: 模拟交易** ✅ — 100万虚拟账户，5 个 DataService actions，26 tests
- [x] **P4-3: 财务报表** ✅ — 利润表/资产负债表/现金流量表 + 关键指标，28 tests
- [ ] **P4-4: Sparkline 迷你图** — Markets 每行行情显示1日迷你趋势线
- [ ] **P4-5: 策略平台/社区** — 回测策略导入/导出 + GitHub open-daily-stock-strategies 仓库
- [ ] **P4-6: data_provider 插件架构** — 付费数据源 Wind/东方财富 Data 可选接入
- [x] **P4-7: CN 因子 AI prompts** ✅ — A股专用分析模板（机构流向/行业轮动/宏观信号），20 tests
- [ ] **P4-8: 微信小程序/移动伴侣** — 微信小程序镜像通知视图 + 轻量查看页面

---

## 四、DataService Action 清单（P0-1 成果）

当前注册 26 个 action：

| Action | 功能 | 来源 |
|--------|------|------|
| `hello` | 健康检查 | 原有 |
| `get_markets` | 获取行情数据 | 原有 |
| `refresh` | 刷新数据 | 原有 |
| `quit` | 退出服务 | 原有 |
| `analyze` | AI 分析 | P0-1 |
| `get_history` | 获取历史数据 | P0-1 |
| `search_news` | 搜索新闻 | P0-1 |
| `get_kline_data` | K线数据 | P1-5 |
| `get_tasks` | 任务列表 | P0-1 |
| `get_task` | 单个任务详情 | P0-1 |
| `cancel_task` | 取消任务 | P0-1 |
| `add_position` | 添加持仓 | P1-4 |
| `remove_position` | 删除持仓 | P1-4 |
| `update_position` | 更新持仓 | P1-4 |
| `get_positions` | 持仓列表 | P1-4 |
| `get_institutional` | 机构动向 | P1-6 |
| `get_dragon_board` | 龙虎榜 | P1-6 |
| `run_backtest` | 运行回测 | P1-7 |
| `get_drawing_data` | K线画线数据 | P4-1 |
| `sim_buy` | 模拟买入 | P4-2 |
| `sim_sell` | 模拟卖出 | P4-2 |
| `sim_summary` | 模拟账户摘要 | P4-2 |
| `sim_history` | 模拟交易历史 | P4-2 |
| `sim_reset` | 重置模拟账户 | P4-2 |
| `get_financials` | 财务报表 | P4-3 |
| `get_key_metrics` | 关键财务指标 | P4-3 |

---

## 五、技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance、efinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API |
| 数据库 | SQLite |
| 进程通信 | stdio JSON / WebSocket |
| 图表 | mplfinance (K线) |
| 打包 | PyInstaller |
| 构建 | GitHub Actions |

---

## 六、项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口
├── src/
│   ├── data_service.py  # 后端守护进程
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── notification.py  # 通知推送（旧，保留兼容）
│   ├── search_service.py # 搜索服务（旧，保留兼容）
│   ├── alert_service.py  # 告警服务
│   ├── portfolio.py     # 持仓成本管理 [P1-4]
│   ├── charts.py        # K线图表生成 [P1-5]
│   ├── institutional.py # 机构动向追踪 [P1-6]
│   ├── backtester.py    # 回测引擎 [P1-7]
│   ├── update_service.py # 自动更新
│   ├── refresh_service.py # 数据刷新
│   ├── notify/          # 通知渠道模块 [P0-2]
│   │   ├── channels/
│   │   │   ├── wechat.py
│   │   │   ├── feishu.py
│   │   │   ├── telegram.py
│   │   │   ├── email.py
│   │   │   └── discord.py
│   │   ├── formatters.py
│   │   └── dispatcher.py
│   └── search_pkg/      # 搜索模块 [P0-3]
│       ├── bocha.py
│       ├── tavily.py
│       ├── serpapi.py
│       └── manager.py
├── tui/                 # TUI 界面
│   ├── app.py          # Textual App
│   └── widgets/        # 各模块视图
├── gui/                 # GUI 界面
│   ├── main.py         # Flet 入口
│   ├── app.py         # StockApp
│   └── pages/         # Markets/Analyze/Tasks/Config/Logs
├── data_provider/       # 数据源适配器
└── .github/
    ├── pyinstaller-hooks/
    └── workflows/       # 构建流程
```

---

## 七、重构优先级说明

### 为什么 P0-1 (DataService) 最优先？
- 当前 DataService 仅支持 4 个 action，但 TUI/GUI 客户端需要更多功能
- 瓶颈不突破，其他功能无法通过 stdio 调用

### 为什么 P0-2 (notification.py) 其次？
- 3112 行单文件，接近维护上限
- 新增通知渠道需要修改多处，耦合严重
- 拆分后可独立测试和复用

### 为什么 P0-3 (search_service.py) 第三？
- 1079 行，逻辑相对独立
- 拆分后可被 DataService 直接调用
- 支持多 Key 负载均衡

---

*最后更新: 2026-05-10 — P0-1~3/P1-1~7/P2-1/P3-1~11/P4-1~4/P4-6~7 完成, P2-2~3/P4-5/P4-8 待实现*