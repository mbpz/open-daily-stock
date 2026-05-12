# open-daily-stock Roadmap

**项目定位：** 本地 PC 端 GUI 应用，无需服务端，打包后双击即可使用所有功能。

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
| AI 分析 | Gemini / OpenAI 兼容 API + 多 Agent + 流式 |
| 数据库 | SQLite + SQLAlchemy ORM |
| 进程通信 | stdio JSON |
| 图表 | mplfinance (K线) |
| 打包 | PyInstaller |

---

## 六、项目结构

```
open-daily-stock/
├── main.py                 # 主入口（GUI）
├── src/
│   ├── data_service.py     # 后端守护进程（30 actions）
│   ├── analyzer.py         # AI 分析器（流式）
│   ├── agents/             # 多 Agent 协同 [P5-5]
│   │   ├── technical.py    # 技术面 Agent
│   │   ├── fundamental.py  # 基本面 Agent
│   │   ├── news.py         # 新闻 Agent
│   │   ├── synthesizer.py  # 合成 Agent
│   │   └── research_agent.py # Agentic Research [P5-9]
│   ├── rag.py              # RAG 上下文构建 [P5-6]
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
│   └── search_pkg/         # 搜索模块 [P0-3]
├── gui/                    # GUI 界面（Flet）
│   └── pages/             # Markets/Analyze/Tasks/Config/Logs/Kline
└── tests/                 # 287+ 测试
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

### P6 — 竞争力强化

- [ ] **P6-1: 策略配置 DSL** — YAML 策略注册表（对标 daily_stock 11 策略）
- [ ] **P6-2: 市场复盘日报** — 自动生成市场概况 + LLM 摘要
- [ ] **P6-3: Agent 反思循环** — 分析结果自检 + 矛盾检测 + 置信度校准
- [ ] **P6-4: Bot/IM 双向交互** — Telegram 命令查行情/触发分析

### P7 — 生态建设

- [ ] **P7-1: 插件架构** — 数据源/通知渠道/AI 模型统一可插拔接口
- [ ] **P7-2: 策略超参优化** — Optuna 自动寻优
- [ ] **P7-3: EventBus 事件驱动** — 模块异步解耦
- [ ] **P7-4: 策略社区** — 策略导入/导出 + GitHub 模板仓库

### 明确不做

- ❌ 实盘交易接口 — 法律风险
- ❌ Pine Script 兼容 — 维护成本高
- ❌ Docker 默认部署 — 与"双击运行"矛盾
- ❌ 纯 Web SaaS — 与本地优先矛盾
- ❌ TUI/CLI 模式 — 已移除，专注 GUI 体验

---

*最后更新: 2026-05-12 — 去 TUI，专注文档 GUI ✅*
