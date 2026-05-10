# Competitive Analysis — open-daily-stock

**Date**: 2026-05-10
**Scope**: GitHub 开源股票分析/量化交易项目全量竞品调研
**方法**: gh API 搜索 + 仓库结构分析 + README 交叉对比

---

## 一、市场全景 (6 大赛道)

### 赛道 1: Web 平台型巨头 (10K+ Stars)

| 项目 | Stars | 语言 | 部署 | 核心定位 |
|------|:-----:|------|------|----------|
| [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | 34.9K | Python | GitHub Actions / Fork | LLM 驱动的 A/H/美股智能分析器 |
| [vnpy](https://github.com/vnpy/vnpy) | 40.3K | Python | pip install | 量化交易平台开发框架 |
| [freqtrade](https://github.com/freqtrade/freqtrade) | 50.0K | Python | Docker | 加密货币自动交易机器人 |
| [TradeMaster](https://github.com/TradeMaster-NTU/TradeMaster) | 2.7K | Python | pip | 强化学习量化交易平台 |

**共同特征**:
- 依赖 GitHub Actions / Docker / pip 等开发者工具链
- 非普通用户安装方式（非双击运行）
- Web UI (Gradio/Streamlit/Flask) 或 Qt 桌面

### 赛道 2: AI Agent 多智能体分析 (新兴赛道, 10-200 Stars)

| 项目 | Stars | 框架 | UI | 关键特性 |
|------|:-----:|------|------|----------|
| [crewai_stock_analysis_system](https://github.com/liangdabiao/crewai_stock_analysis_system) | 163 | CrewAI | Web (Flask) | 多 Agent 协作、批量处理、实时监控、预警 |
| [llm-stock-team-analyzer](https://github.com/jason8745/llm-stock-team-analyzer) | 33 | LangGraph | CLI + Docker | 技术分析/新闻情绪/综合推荐 Agent |
| [AlphaAnalyst](https://github.com/kbhujbal/AlphaAnalyst-open-source-autonomous-equity-research-agent) | 26 | Custom | FastAPI + Next.js | DCF 估值、peer comparables、pgvector RAG |
| [QuantScope](https://github.com/Kai-dev7/QuantScope) | 22 | Custom | Streamlit + Next.js | 可配置 LLM 工作流、MCP server |
| [TradingGoose](https://github.com/TradingGoose/TradingGoose.github.io) | 61 | Custom | Web | 多 Agent 金融交易框架 |
| [LLM-Based-Multi-Agent-Stock-Analysis](https://github.com/DiLiuNEUexpresscompany/LLM-Based-Multi-Agent-Stock-Analysis-and-Investment-Advisor) | 24 | LangGraph | CLI | 股价分析 + 新闻 + 投资报告 |

**共同特征**:
- 全部基于 Web/CLI，无桌面应用
- 研究报告导向（生成 MD/PDF 报告）
- 美股为主，缺乏 A 股深度支持

### 赛道 3: CMD + Web 混合型 (100-500 Stars)

| 项目 | Stars | 语言 | 界面 | 关键特性 |
|------|:-----:|------|------|----------|
| [AI-Kline](https://github.com/QuantMLResearch/AI-Kline) | 325 | Python | CMD + Web + MCP | K 线图 + 技术指标 + AI 预测 |

### 赛道 4: 个人开发者 AI 分析工具 (<20 Stars)

| 项目 | Stars | 关键特性 |
|------|:-----:|----------|
| [value-investing-ai-agent](https://github.com/nicdun/value-investing-ai-agent) | 16 | Alpha Vantage + LLM 基本面分析 |
| [stock-assist](https://github.com/vibheksoni/stock-assist) | 11 | Flask + agentic AI + 实时行情 |
| [ai-stock-report](https://github.com/chienchandler/ai-stock-report) | 9 | A 股 AI 日报自动推送 |
| [CrewAi-Gemini-Stock-Analyser](https://github.com/MukulGupta121190/CrewAi-Gemini-Stock-Analyser) | 5 | CrewAI + Gemini + DuckDuckGo |
| [ai-stock-analyzer-Desktop](https://github.com/stratoslig/ai-stock-analyzer-Desktop) | 2 | Desktop + Gemini/Ollama |
| [StockAgent](https://github.com/DevanshuSave/StockAgent) | 2 | Claude API + yfinance + ChromaDB |

### 赛道 5: 量化平台 (>200 Stars)

| 项目 | Stars | 关键特性 |
|------|:-----:|----------|
| [AlphaSuite](https://github.com/rsandx/AlphaSuite) | 218 | 策略构建/测试/部署，专业级 |

### 赛道 6: open-daily-stock 独占赛道

**唯一 TUI+GUI 双模式 + PyInstaller 桌面打包 + 机构追踪 + 画线 + 模拟交易的组合**

---

## 二、核心技术架构对比

### 2.1 架构模式

| 维度 | open-daily-stock | daily_stock_analysis | crewai_stock | llm-stock-team-analyzer | QuantScope |
|------|:---:|:---:|:---:|:---:|:---:|
| **架构** | DataService fork + stdio JSON IPC | 单体 FastAPI + scheduler | CrewAI Flow + Web | LangGraph StateGraph | FastAPI + Streamlit + Next.js |
| **进程模型** | 多进程 (TUI/GUI + DataService) | 单进程 + 子线程 | 单进程 | 单进程 | 前后端分离 |
| **通信** | stdio JSON | HTTP REST | Python 函数调用 | LangGraph channels | HTTP REST |
| **数据源** | AkShare + YFinance + efinance | 多源聚合 (EFMI/AkShare 等) | YFinance + 自定义采集 | YFinance | YFinance + Alpha Vantage |
| **数据库** | SQLite (本地) | DuckDB + parquet (本地) | 无持久化 | 无 | PostgreSQL + Redis |
| **部署** | PyInstaller 打包 | GitHub Actions / systemd | pip + Web | Docker | Docker Compose |

### 2.2 AI/LLM 架构深度对比

| 维度 | open-daily-stock | daily_stock_analysis | crewai_stock | llm-stock-team-analyzer | QuantScope |
|------|:---:|:---:|:---:|:---:|:---:|
| **LLM 框架** | 直接 API 调用 | 自研 Agent Framework | CrewAI | LangGraph | 自研 adapter + LangGraph |
| **Agent 模型** | 单一分析 Agent | Orchestrator + Executor + Skills + Tools | CrewAI Crew + Task | 4 Agent Graph (Analyst×3 + Trader) | Multi-agent + Quality Gates |
| **Agent 记忆** | 无 | ✅ Memory + Conversation | CrewAI 内置 | LangGraph 状态 | ✅ |
| **工具系统** | 函数调用 | ✅ Skills + Tools 注册 | CrewAI Tools | 函数工具 | ✅ Skills + Tools |
| **策略系统** | 无 (仅 MA 交叉回测) | ✅ 11 种 YAML 策略 | 无 | 无 | 无 |
| **流式输出** | ✅ (P5-1 完成) | ❌ | ❌ | ❌ | ❌ |
| **多模型** | Gemini + OpenAI 兼容 | 8+ 模型切换 | Gemini | Groq LLM | Claude + GPT-4o |
| **MCP 支持** | ✅ (stdio JSON bridge) | ❌ | ❌ | ❌ | ✅ MCP Server |
| **RAG** | 无 | ❌ | ❌ | ❌ | ✅ pgvector |

### 2.3 交互/UX 对比

| 维度 | open-daily-stock | daily_stock_analysis | crewai_stock | vnpy | freqtrade |
|------|:---:|:---:|:---:|:---:|:---:|
| **TUI** | ✅ Textual | ❌ | ❌ | ❌ | ❌ |
| **GUI** | ✅ Flet | ❌ | ❌ | ✅ Qt (PySide6) | ❌ |
| **Web UI** | ❌ | ✅ Gradio | ✅ Flask | ❌ | ✅ React |
| **IM Bot** | ❌ | ✅ Telegram/Discord/微信 | ❌ | ❌ | ✅ Telegram |
| **移动端** | ❌ | ❌ | ❌ | ❌ | ✅ (Telegram) |
| **快捷键** | ✅ (1-5/Tab/r/q) | ❌ | ❌ | ✅ (Qt 标准) | ❌ |
| **主题** | 基础 | ✅ 亮/暗 | ❌ | ✅ Qt 主题 | ✅ |
| **安装** | 双击 PyInstaller | Fork GitHub | pip install | pip install | Docker |
| **自动更新** | ✅ GitHub Releases | ❌(Git Sync) | ❌ | ❌ | ✅ Docker |

### 2.4 产品功能维度

| 功能 | open-daily-stock | daily_stock_analysis | vnpy | freqtrade | crewai_stock |
|------|:---:|:---:|:---:|:---:|:---:|
| A 股实时行情 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 港股/美股 | ✅ | ✅ | ❌ | ❌(crypto) | ❌ |
| AI 决策分析 | ✅ 仪表盘 | ✅ 多模型 | ❌(ML因子) | ✅(FreqAI ML) | ✅ |
| 多 Agent 协作 | ❌ | ✅ 计划中 | ❌ | ❌ | ✅ CrewAI |
| 策略回测 | ✅ MA 交叉 | ✅ 11 策略 | ✅ 完整 CTA | ✅ 完整 + 超参优化 | 基础 |
| 策略配置化 | ❌ | ✅ YAML | ✅ | ✅ JSON | ❌ |
| 模拟交易 | ✅ | ❌ | ✅ 纸交易 | ✅ Dry Run | ❌ |
| 实盘交易 | ❌ | ❌ | ✅ CTP | ✅ 交易所 | ❌ |
| K 线/图表 | ✅ mplfinance | ❌ | ✅ pyqtgraph | ✅ Plotly | ❌ |
| 画线工具 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 机构追踪 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 龙虎榜 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 持仓管理 | ✅ 盈亏计算 | ❌ | ✅ 完整 | ✅ | ❌ |
| 自选股 | ✅ | ✅ | ✅ | ✅(watchlist) | ❌ |
| 市场复盘 | ❌ | ✅ 日报 | ❌ | ❌ | ❌ |
| 新闻聚合/情绪 | ❌ | ✅ | ❌ | ❌ | ✅ |
| 通知推送 | ✅ 5 渠道 | ✅ 多平台 | ❌ | ✅ Telegram | ✅ 预警 |
| 插件架构 | ❌ | ❌ | ✅ Gateway | ✅ Plugins | ❌ |
| i18n | ✅ 中英 | ✅ 中英 | ✅ 中英 | ✅ | ❌ |
| 定时任务 | ✅ cron 式 | ✅ 完整 scheduler | ✅ 定时 | ✅ | ✅ |

---

## 三、Gap Analysis — 竞品有而我们缺的

### 高价值 Gap (建议 P6 实现)

#### G1: 策略配置系统 (对标 daily_stock_analysis)
- **现状**: 只有 MA 交叉一种策略，硬编码
- **竞品**: daily_stock_analysis 有 11 种 YAML 策略 (bull_trend, dragon_head, emotion_cycle, chan_theory, wave_theory...)
- **价值**: 用户可自行扩展策略，无需改代码
- **方案**: `strategies/` 目录 + YAML DSL + 策略注册表

#### G2: 多 Agent 分析架构 (对标 crewai_stock / llm-stock-team-analyzer)
- **现状**: 单一 LLM 调用，无 Agent 分工
- **竞品**: 技术分析 Agent + 新闻情绪 Agent + 估值 Agent + 综合推荐 Agent
- **价值**: 分析深度从单一维度提升到多维度交叉验证
- **方案**: LangGraph StateGraph + 4 专业 Agent

#### G3: Bot/IM 交互 (对标 daily_stock_analysis / freqtrade)
- **现状**: 通知仅单向推送
- **竞品**: Telegram/Discord/微信 Bot 支持双向命令交互
- **价值**: 移动端查行情、触发分析、接收预警
- **方案**: `bot/` 模块 + Telegram/Discord/企业微信 Bot

#### G4: 市场复盘日报 (对标 daily_stock_analysis)
- **现状**: 无每日市场总结
- **竞品**: daily_stock_analysis 自动生成市场概况 + 热点板块 + 涨跌统计
- **价值**: 用户开机即见今日市场全景
- **方案**: market_review 定时任务 + LLM 摘要

#### G5: RAG 知识增强 (对标 AlphaAnalyst / QuantScope)
- **现状**: LLM 分析仅基于当前数据
- **竞品**: AlphaAnalyst 用 pgvector 做历史研报检索增强
- **价值**: 历史相似形态检索、研报知识库
- **方案**: ChromaDB/SQLite-vec + 研报嵌入

### 中价值 Gap (P7 候补)

#### G6: 插件架构 (对标 vnpy / freqtrade)
- **现状**: 所有功能硬编码
- **竞品**: vnpy Gateway 插件、freqtrade Plugins
- **价值**: 社区贡献策略/数据源/通知渠道
- **方案**: 插件发现机制 + 标准化接口

#### G7: 策略参数优化 (对标 freqtrade)
- **现状**: 回测用固定参数
- **竞品**: freqtrade 超参优化 (Hyperopt)
- **价值**: 自动找到最优策略参数
- **方案**: Optuna 集成

#### G8: 移动端访问 (对标 freqtrade Telegram)
- **现状**: 仅 PC 端
- **竞品**: freqtrade 通过 Telegram Bot 实现移动端
- **价值**: 通勤/外出时查看
- **方案**: 依赖 G3 Bot 交互实现

---

## 四、open-daily-stock 独有优势 (护城河)

这些是竞品**全部没有**的能力:

| 独有能力 | 说明 | 竞品情况 |
|----------|------|----------|
| **TUI+GUI 双模式** | 同一套后端，终端/图形界面自由切换 | 竞品均为单一模式 |
| **一键桌面安装** | PyInstaller 打包，非开发者友好 | 竞品需 pip/Docker/GitHub Actions |
| **机构追踪** | 大股东增减持、机构调研、龙虎榜 | 所有竞品均无 |
| **画线工具** | K 线图上手动画趋势线/支撑阻力 | 仅 TradingView 有，开源竞品无 |
| **模拟交易** | 虚拟资金交易 + 收益跟踪 | vnpy/freqtrade 有但面向实盘 |
| **全本地优先** | 数据 100% 不离开本机 | 竞品依赖 GitHub Secrets/云 API |
| **5 渠道通知** | 企业微信/飞书/Telegram/邮件/Discord | 竞品最多 2 个 |
| **A 股深度** | 龙虎榜/机构调研/大股东增减持 | 竞品要么不做 A 股，要么仅行情 |

---

## 五、推荐实施路线

### P6: 竞争力强化 (2026-Q2)

```
P6-1: 策略配置系统 (对标 daily_stock_analysis)     — 3天
P6-2: 多 Agent 分析架构 (对标 crewai/langgraph)     — 5天
P6-3: Bot/IM 双向交互 (对标 freqtrade bot)         — 3天
P6-4: 市场复盘日报 (对标 daily_stock_analysis)     — 2天
P6-5: RAG 历史知识增强 (对标 AlphaAnalyst)         — 4天
```

### P7: 生态建设 (2026-Q3)

```
P7-1: 插件架构 (对标 vnpy/freqtrade)
P7-2: 策略参数优化 (Optuna 集成)
P7-3: 更多数据源 (东方财富/新浪财经)
P7-4: 社区策略市场
```

### 架构演进路线图

```
当前                           P6                              P7
───────                    ──────────                      ──────────
单一 Agent ──────────→ 多 Agent 协作              → Agent 市场
单一策略  ──────────→ YAML 策略配置               → 社区策略市场
单向通知  ──────────→ Bot 双向交互                → 移动端支持
即时分析  ──────────→ 市场复盘 + RAG 增强          → 自动化日报
硬编码    ──────────→ 标准化接口                  → 插件架构
```

---

## 六、数据来源

- GitHub API search: `stock+analysis+AI+LLM`, `quantitative+trading+platform`, `stock+agent+multi-agent`
- 仓库结构分析: `gh api repos/{owner}/{repo}/contents/` 递归
- 元数据: `gh repo view` + `stargazerCount`, `forkCount`, `pushedAt`, `repositoryTopics`
- README 交叉对比: 关键特性、架构、部署方式

**调研覆盖**: 25+ GitHub 仓库, 6 个赛道, 4 个维度 (架构/原理/实现/交互/产品)
