# open-daily-stock Roadmap

**项目定位：** 本地 PC 端 GUI 应用，无需服务端，打包后双击即可使用所有功能。

**路线图版本：** v0.4.0（P0-P5 已完成） → **v0.5.0**（P6 竞争力强化） → **v0.6.0**（P7 架构深化）

---

## 一、架构概览

```
open-daily-stock (GUI)
    ↓
自动 fork DataService (后端守护进程)
    ↓
←── DataService (30 actions) ──→
```

---

## 二、已完成功能总览

| 功能模块 | 状态 | 来源 |
|---------|:----:|------|
| A股/港股/美股实时行情 | ✅ | P0 |
| AI 分析（Gemini + OpenAI，流式输出） | ✅ | P5-1 |
| 多 Agent 协同分析（技术/基本面/新闻+合成） | ✅ | P5-5 |
| RAG 知识库（FTS5 全文检索） | ✅ | P5-6 |
| Command Palette（Ctrl+K 模糊搜索） | ✅ | P5-7 |
| 通知中心（Toast + 历史记录） | ✅ | P5-8 |
| Agentic Research（LLM 自主多步研究） | ✅ | P5-9 |
| 因子分析引擎（PE/PB/momentum/volume/MA/RSI） | ✅ | P5-10 |
| 持仓管理 | ✅ | P1-4 |
| K线回放 | ✅ | P1-5 |
| 机构追踪（股东/调研/龙虎榜） | ✅ | P1-6 |
| 策略回测（MA 交叉） | ✅ | P1-7 |
| 模拟交易（100万虚拟账户） | ✅ | P4-2 |
| 画线工具（斐波那契/支撑阻力） | ✅ | P4-1 |
| 财务报表 | ✅ | P4-3 |
| Sparkline 迷你图 | ✅ | P4-4 |
| 5 渠道通知（企微/飞书/TG/邮件/Discord） | ✅ | P0 |
| MCP Server（stdio JSON-RPC 2.0） | ✅ | P5-2 |
| 多语言（zh_CN/en/ja_JP/ko_KR） | ✅ | P2-3 |
| 主题切换（深色/浅色） | ✅ | P2-2 |

---

## 三、P5 生态演进（2026 全部完成 ✅）

*10 项任务，全部实现：*

### P5-1 ~ P5-4 即时优先 ✅

| 任务 | 说明 | 测试 |
|------|------|------|
| **P5-1: Streaming LLM** | token-by-token 流式输出，感知延迟 8s→1s | 25 |
| **P5-2: MCP Server Bridge** | 37 tools 包装为 MCP Tool，`--mcp-server` 模式 | 39 |
| **P5-3: Homebrew + winget 分发** | `brew install` / `winget install` | — |
| **P5-4: Demo Data 免配置** | 5 只热门股 + K线历史 + AI 样例 | 25 |

### P5-5 ~ P5-8 中期增强 ✅

| 任务 | 说明 | 测试 |
|------|------|------|
| **P5-5: 多 Agent 模式** | 3 并行 specialist (技术面/基本面/新闻) + 1 合成 agent | 41 |
| **P5-6: RAG 知识库** | SQLite FTS5 全文索引 + LIKE fallback for Chinese | 15 |
| **P5-7: Command Palette** | Ctrl+K 模糊搜索所有 action | 37 |
| **P5-8: 通知中心** | SQLite notifications 表 + Toast + 通知历史 | 26 |

### P5-9 ~ P5-10 长期探索 ✅

| 任务 | 说明 | 测试 |
|------|------|------|
| **P5-9: Agentic Research** | ResearchAgent + LLM tool-calling loop，LLM 自主多步研究 | 32 |
| **P5-10: 因子分析引擎** | 6 因子 (PE/PB/momentum/volume/MA/RSI)，IC/IR 分析 | 47 |

**P5 测试总计：287+**

---

## 四、DataService Action 清单（30 actions）

| Action | 功能 | 来源 |
|--------|------|------|
| `hello` | 健康检查 | 原有 |
| `get_markets` | 获取行情数据 | 原有 |
| `refresh` | 刷新数据 | 原有 |
| `quit` | 退出服务 | 原有 |
| `analyze` | AI 分析（流式） | P5-1 |
| `get_history` | 获取历史数据 | P0-1 |
| `search_news` | 搜索新闻 | P0-1 |
| `get_tasks` | 任务列表 | P0-1 |
| `get_task` | 单个任务详情 | P0-1 |
| `cancel_task` | 取消任务 | P0-1 |
| `get_kline_data` | K线数据 | P1-5 |
| `get_drawing_data` | K线画线数据 | P4-1 |
| `add_position` | 添加持仓 | P1-4 |
| `remove_position` | 删除持仓 | P1-4 |
| `update_position` | 更新持仓 | P1-4 |
| `get_positions` | 持仓列表 | P1-4 |
| `get_institutional` | 机构动向 | P1-6 |
| `get_dragon_board` | 龙虎榜 | P1-6 |
| `run_backtest` | 运行回测 | P1-7 |
| `sim_buy` | 模拟买入 | P4-2 |
| `sim_sell` | 模拟卖出 | P4-2 |
| `sim_summary` | 模拟账户摘要 | P4-2 |
| `sim_history` | 模拟交易历史 | P4-2 |
| `sim_reset` | 重置模拟账户 | P4-2 |
| `get_financials` | 财务报表 | P4-3 |
| `get_key_metrics` | 关键财务指标 | P4-3 |
| `rag_search` | FTS5 知识库检索 | P5-6 |
| `research` | Agentic Research 多步研究 | P5-9 |
| `get_factor_value` | 单因子数值 | P5-10 |
| `analyze_factor_ic` | 因子 IC/IR 分析 | P5-10 |
| `get_factor_rankings` | 因子排名 | P5-10 |

---

## 五、技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance |
| AI 分析 | DeepSeek（OpenAI 兼容 API）+ 多 Agent + 流式 |
| 数据库 | SQLite + SQLAlchemy ORM |
| 进程通信 | stdio JSON → WebSocket（v0.6.0 升级） |
| 图表 | mplfinance (K线静态) / pyqtgraph（v0.6.0 实时） |
| 打包 | PyInstaller |

---

## 六、项目结构

```
open-daily-stock/
├── main.py                 # 主入口（GUI）
├── src/
│   ├── data_service.py     # 后端守护进程（40+ actions）
│   ├── analyzer.py         # AI 分析器（流式）
│   ├── agents/             # 多 Agent 协同 [P5-5]
│   │   ├── orchestrator.py # 并行协调器
│   │   ├── technical_agent.py  # 技术面 Agent
│   │   ├── fundamental_agent.py # 基本面 Agent
│   │   ├── news_agent.py       # 新闻 Agent
│   │   ├── synthesizer_agent.py # 合成 Agent
│   │   └── research_agent.py  # Agentic Research [P5-9]
│   ├── rag_store.py        # FTS5 知识库 [P5-6]
│   ├── factor_engine.py    # 因子分析引擎 [P5-10]
│   ├── commands.py          # 命令统一定义 [P5-7]
│   ├── notification_center.py # 通知中心 [P5-8]
│   ├── mcp_tools.py        # MCP Tool 定义 [P5-2]
│   ├── mcp_server.py       # MCP stdio Server [P5-2]
│   ├── config.py           # 配置管理
│   ├── pipeline.py         # 分析管线
│   ├── portfolio.py        # 持仓成本管理 [P1-4]
│   ├── charts.py           # K线图表 [P1-5]
│   ├── institutional.py    # 机构追踪 [P1-6]
│   ├── backtester.py       # 回测引擎 [P1-7]
│   ├── notify/             # 通知渠道 [P0-2]
│   │   └── channels/      # wechat/feishu/telegram/email/discord
│   └── data_provider/      # 多源数据（插件架构）
│       ├── akshare_fetcher.py
│       ├── yfinance_fetcher.py
│       ├── efinance_fetcher.py
│       └── plugin.py       # ProviderRegistry
├── gui/                    # GUI 界面（Flet）
│   ├── app.py              # StockApp (NavigationRail)
│   └── pages/              # markets/analyze/tasks/config/logs/chart/strategies/notifications
└── tests/                  # 750+ 测试
```

---

## 七、竞品定位

**open-daily-stock = 桌面体验最佳的 AI 股票分析工具**

| 核心差异 | open-daily-stock | 雪球/同花顺 | TradingView | daily_stock_analysis |
|----------|:---:|:---:|:---:|:---:|
| 安装方式 | PyInstaller 双击 | 云端 | Web | GitHub Actions |
| 本地数据 | ✅ 全部本地 | ❌ 云端 | ❌ 云端 | ❌ 云端 |
| 机构追踪 | ✅ | ✅ | ❌ | ❌ |
| 画线工具 | ✅ | ✅ | ✅ | ❌ |
| 模拟交易 | ✅ | ❌ | ✅ | ❌ |
| 通知渠道 | 5 个 | 1-2 个 | 1-2 个 | 3 个 |
| Command Palette | ✅ | ❌ | ❌ | ❌ |
| AI 多 Agent | ✅ | ❌ | ❌ | ✅ (8模型) |
| RAG 知识库 | ✅ | ❌ | ❌ | ❌ |

---

## 八、待完成任务

### 设计原则（贯穿 P6/P7）

- **本地 PC 桌面优先** — 不向 Web/Docker 妥协。打包后双击即用是核心体验。
- **AI 模型精简** — 仅维护 DeepSeek（OpenAI 兼容 API），不扩展 Claude/通义千问/Ollama 等多模型支持。减少维护矩阵，聚焦分析质量。
- **深度优于广度** — 每个模块做深而非做多。策略引擎、Agent 反思、市场复盘都要做到真正可用。

---

### P6 — 竞争力强化

| 任务 | 说明 | 对标/参考 | 测试目标 |
|------|------|-----------|:---:|
| **P6-1: 策略引擎升级** | 从 7 个 YAML DSL 扩展到完整策略基类。支持 RSI/MACD/Bollinger/KDJ 等技术指标策略、多条件组合、止盈止损参数化。对标 freqtrade 的策略类架构 | freqtrade Strategy base class | 30+ |
| **P6-2: 市场复盘日报** | 每日自动生成：指数表现、涨跌统计、板块强弱、资金流向 + LLM 自然语言摘要。对标 daily_stock_analysis 的市场复盘功能 | daily_stock_analysis | 20+ |
| **P6-3: Agent 反思循环** | 分析完成后自检：信号一致性验证（技术面 vs 基本面矛盾检测）、置信度校准（历史准确率加权）、未覆盖风险提示。二轮 LLM call 做 critical review | 原创能力 | 25+ |
| **P6-4: Bot/IM 双向交互** | Telegram/Discord Bot 支持命令式查询：`/quote 600519` 查行情、`/analyze 600519` 触发分析、`/alert 600519 >1800` 设价格告警。对标 freqtrade Telegram RPC | freqtrade Telegram RPC | 20+ |

### P6 架构偿还（与 P6 功能并行）

| 任务 | 说明 | 优先级 |
|------|------|:---:|
| **per-request 超时机制** | handler thread pool + 30s timeout，防止单请求挂死拖累整个 DataService daemon | 🔴 P0 |

---

### P7 — 架构深化

| 任务 | 说明 | 对标/参考 | 测试目标 |
|------|------|-----------|:---:|
| **P7-1: 统一存储层** | 全部迁移到 SQLAlchemy ORM。消除 storage.py 与 data_service.py 双存储混用，统一事务语义、migration 路径。对标 freqtrade persistence 层 | freqtrade persistence/ | — |
| **P7-2: WebSocket IPC** | DataService 支持 WebSocket server，替代纯 stdio JSON 单向阻塞。支持双向异步推送、streaming 复用。对标 freqtrade WebSocket RPC | freqtrade RPC WebSocket | 15+ |
| **P7-3: EventBus 事件驱动** | 模块间异步解耦。替换当前硬编码 handler 调用。支持事件订阅/发布、优先级队列。对标 vnpy EventBus | vnpy trader/event.py | 20+ |
| **P7-4: 插件架构** | 数据源（AkShare/YFinance/efinance）、通知渠道（企微/飞书/TG/邮件/Discord）、AI 模型统一可插拔接口。依赖注入 + Provider 注册表 | freqtrade resolvers/ | 25+ |
| **P7-5: 策略超参优化** | Optuna 贝叶斯优化自动寻优策略参数（MA周期、RSI阈值、止损比例）。对标 freqtrade Hyperopt | freqtrade Hyperopt | 15+ |
| **P7-6: 策略社区** | 策略 JSON 导入/导出标准格式、GitHub 模板仓库（open-daily-stock-strategies）、策略市场/排行榜 | freqtrade 社区 | 10+ |

### P7 性能与质量

| 任务 | 说明 | 对标/参考 |
|------|------|-----------|
| **测试体系建设** | 目标 500+ 测试，覆盖率 >80%，CI/CD 集成。对标 freqtrade 2000+ 测试体系 | freqtrade tests/ |
| **Rust 加速路径** | 回测引擎关键路径用 Rust FFI（PyO3/maturin）。数据处理、因子计算等 CPU 密集场景。对标 QUANTAXIS qapro-rs | QUANTAXIS qapro-rs |
| **社区增长策略** | GitHub Actions 自动化模板（一键 fork 部署）、多语言 README（English/繁中）、视频教程（YouTube/B站）、Product Hunt 发布 | — |

---

## 九、P6/P7 详细设计

### P6-1: 策略引擎升级

```
当前：strategies/*.yaml (7 个静态 YAML)
目标：src/strategies/ 策略基类 + 参数化

src/strategies/
├── __init__.py
├── base.py              # BaseStrategy 抽象基类
├── registry.py          # StrategyRegistry 注册表
├── builtin/
│   ├── ma_cross.py      # 均线金叉/死叉
│   ├── rsi_strategy.py  # RSI 超买超卖
│   ├── macd_strategy.py # MACD 金叉/背离
│   ├── bollinger.py     # 布林带突破
│   ├── kdj_strategy.py  # KDJ 指标
│   ├── volume_break.py  # 放量突破
│   ├── trend_follow.py  # 趋势跟随
│   └── mean_revert.py   # 均值回归
└── community/           # 社区策略 JSON 加载
```

**BaseStrategy 接口：**
- `entry_signal(df) → bool` — 入场条件
- `exit_signal(df, position) → bool` — 出场条件
- `get_indicators() → List[str]` — 所需指标列表
- `get_params() → Dict` — 可调参数

### P6-2: 市场复盘日报

```
src/core/market_review.py  (已有，需增强)

每日自动内容：
1. 指数概览 — 上证/深证/创业板 涨跌幅 + 成交量
2. 涨跌统计 — 涨跌比、涨停/跌停数
3. 板块强弱 — 行业板块排名（AkShare 板块接口）
4. 资金流向 — 北向资金/主力资金
5. LLM 摘要 — DeepSeek 生成自然语言市场概述
6. 推送 — 通过现有通知渠道推送日报

触发方式：GUI 手动触发 + 收盘后自动（15:30 定时）
```

### P6-3: Agent 反思循环

```
分析流程增强：

1. 多 Agent 并行分析（现有）
2. Synthesizer 合成报告（现有）
3. 【新增】Reflector 自检：
   a. 信号一致性 — 技术面看多 + 基本面看空 → 标记矛盾
   b. 置信度校准 — 基于历史分析准确率加权
   c. 风险未覆盖 — 政策/流动性/国际形势等外部风险提示
4. 二次 LLM call 做 critical review
5. 输出：主报告 + 反思附注

新增文件：src/agents/reflector_agent.py
```

### P6-4: Bot/IM 双向交互

```
src/bot/  (已有目录结构，需实现)
├── __init__.py
├── base.py              # BotBase 抽象基类
├── dispatcher.py        # 命令分发器
└── platforms/
    ├── __init__.py
    ├── telegram.py      # Telegram Bot（python-telegram-bot）
    └── discord.py        # Discord Bot（discord.py）

支持命令：
/quote <code>        — 实时行情
/analyze <code>      — 触发 AI 分析
/alert <code> <cond> — 设置价格告警
/positions           — 查看持仓
/review              — 市场复盘日报
```

---

## 十、明确不做

- ❌ 实盘交易接口 — 法律风险
- ❌ Pine Script 兼容 — 维护成本高
- ❌ Docker 默认部署 — 与"双击运行"矛盾
- ❌ 纯 Web SaaS / Streamlit — 与本地桌面优先矛盾
- ❌ TUI/CLI 模式 — 已移除，专注 GUI 体验
- ❌ 多 AI 模型扩展（Claude/通义千问/Ollama） — 聚焦 DeepSeek，减少维护矩阵

---

*最后更新: 2026-05-13 — P6/P7 详细规划，v0.5.0/v0.6.0 路线图*