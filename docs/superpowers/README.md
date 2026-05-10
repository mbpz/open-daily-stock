# Superpowers — open-daily-stock Roadmap Design

**日期:** 2026-05-10
**覆盖:** P0–P7 全部已完成 + P5-5~P5-10 + P6 + P7 待办
**来源:** [competitive-analysis.md](../plans/2026-05-10-competitive-analysis.md) — 25+ GitHub 仓库全量调研

---

## 一、项目定位

**open-daily-stock** = 本地 PC 端 TUI + GUI 双模式应用，对比雪球/同花顺的云端模式，真正保护数据隐私。

### 护城河（竞品均不具备）

| 独有能力 | 说明 |
|----------|------|
| **TUI+GUI 双模式** | 同一后端，终端/图形界面自由切换 |
| **PyInstaller 双击安装** | 非开发者友好，竞品需 pip/Docker/GitHub |
| **机构追踪 + 龙虎榜** | A 股深度功能，所有竞品缺失 |
| **画线工具** | 斐波那契回撤 + 支撑阻力位，仅 TradingView 有 |
| **模拟交易** | 100 万虚拟账户，即装即用 |
| **5 渠道通知** | 企微/飞书/Telegram/邮件/Discord |

---

## 二、已完成功能 (P0–P5-4)

| 阶段 | 状态 | 核心成果 |
|------|------|----------|
| P0 | ✅ | DataService Action 扩展 (4→26)、notification/search 模块化拆解 |
| P1 | ✅ | 数据层增强、TUI/GUI 复用、错误恢复、持仓管理、K线回放、机构追踪、回测引擎 |
| P2 | ✅ | 快捷键配置化、主题切换、多语言 |
| P3 | ✅ | 扩展技术指标、选股器、Alert UI、AI Verdict Badge、Sparkline 迷你图 |
| P4 | ✅ | 画线工具、模拟交易、财务报表、Sparkline、策略平台、data_provider 插件、CN 因子 prompts |
| P5-1 | ✅ | Streaming LLM 响应（token-by-token，延迟 8s→1s） |
| P5-2 | ✅ | MCP Server Bridge（37 tools 包装为 MCP Tool） |
| P5-3 | ✅ | Homebrew + winget 分发 |
| P5-4 | ✅ | Demo Data 免配置体验 |

---

## 三、待完成功能 (P5-5 ~ P7)

### P5 中期增强

| ID | 任务 | 对标 | 工作量 | 优先级 |
|----|------|------|:------:|:------:|
| P5-5 | Deep Analysis 多 Agent 模式 | llm-stock-team-analyzer | 中高 | 高 |
| P5-6 | RAG 知识库 | QuantScope pgvector | 中 | 中 |
| P5-7 | Command Palette 命令面板 | VSCode/Rome tools | 中 | 中 |
| P5-8 | In-App 通知中心 | native OS notifications | 中 | 中低 |

### P5 长期探索

| ID | 任务 | 对标 | 工作量 | 优先级 |
|----|------|------|:------:|:------:|
| P5-9 | Agentic Research Mode | AutoGPT-style | 高 | 低 |
| P5-10 | 因子分析引擎 | AlphaGPT/FactorHub | 高 | 低 |

### P6 竞争力强化（竞品分析驱动）

| ID | 任务 | 对标 | 工作量 | 优先级 |
|----|------|------|:------:|:------:|
| P6-1 | 策略配置系统 YAML DSL | daily_stock_analysis 11策略 | 中 | 高 |
| P6-2 | 多 Agent 分析架构 (LangGraph) | llm-stock-team-analyzer | 高 | 高 |
| P6-3 | Bot/IM 双向交互 | freqtrade Telegram / daily_stock 微信 | 中 | 高 |
| P6-4 | 市场复盘日报 | daily_stock_analysis 日报 | 低 | 中 |
| P6-5 | RAG 历史知识增强 | AlphaAnalyst pgvector / QuantScope | 中 | 中 |
| P6-6 | Agent 反思循环 | llm-stock-team-analyzer reflection | 中 | 中 |

### P7 生态建设

| ID | 任务 | 对标 | 工作量 | 优先级 |
|----|------|------|:------:|:------:|
| P7-1 | 插件架构 | vnpy Gateway / freqtrade Plugins | 高 | 中 |
| P7-2 | 策略超参优化 | freqtrade Hyperopt | 中 | 中 |
| P7-3 | EventBus 事件驱动 | vnpy EventBus | 中 | 低 |
| P7-4 | 策略社区 | freqtrade 策略市场 | 高 | 低 |
| P7-5 | Docker 镜像（可选） | freqtrade | 低 | 低 |

---

## 四、技术架构路线图

```
当前                           P6                              P7
────────────────────────    ──────────────────────────    ──────────────────────────
单一 LLM 调用            →  多 Agent 协作 (P6-2)        →  Agent 市场 (P7-4)
MA 交叉策略              →  YAML 策略 DSL (P6-1)       →  策略社区 (P7-4)
单向推送通知             →  Bot 双向交互 (P6-3)         →  移动端支持
即时分析                 →  市场复盘 + RAG 增强 (P6-4/5) →  自动化日报
无 Agent 反思            →  Reflection 循环 (P6-6)     →  自主研究 (P5-9)
硬编码 handler           →  EventBus (P7-3)             →  插件架构 (P7-1)
```

---

## 五、Plan 文件索引

| Plan 文件 | 状态 | 描述 |
|-----------|:-----:|------|
| `plans/2026-05-09-data-service-actions.md` | ✅ | P0-1 DataService Action 扩展方案 |
| `plans/2026-05-09-notification-modularization.md` | ✅ | P0-2 notification.py 模块化拆解 |
| `plans/2026-05-09-search-modularization.md` | ✅ | P0-3 search_service.py 模块化 |
| `plans/2026-05-10-p1-2-p1-3-plan.md` | ✅ | P1-2/3 共享代码 + 错误恢复方案 |
| `plans/2026-05-10-p5-roadmap-design.md` | ✅ | P5 生态演进路线（已部分实现） |
| `plans/2026-05-10-competitive-analysis.md` | ✅ | 25+ 仓库竞品全量调研 |

## 六、Design Spec 文件索引

| Spec 文件 | 状态 | 描述 |
|-----------|:-----:|------|
| `specs/multi-agent-architecture.md` | ✅ | LangGraph 4-Agent 架构设计 |
| `specs/2026-05-10-p5-roadmap-design.md` | ✅ | P5 生态演进详细设计 |
| `specs/2026-05-10-roadmap-enhancement-design.md` | ✅ | P6/P7 增强设计 |

---

## 七、实施顺序建议

```
第一周: P5-5 (多 Agent) + P5-6 (RAG)    ← 并行开发
第二周: P6-1 (策略 DSL) + P6-4 (日报)   ← 低 hanging fruit
第三周: P6-3 (Bot 交互)                 ← 高价值差异化
第四周: P5-7 (Command Palette) + P5-8  (通知中心)  ← UX 收尾
第五周: P6-6 (Agent 反思) + P5-9 (Agentic Research) ← AI 深度
```

---

*最后更新: 2026-05-10 — P0-P5-4 完成, P5-5~P7 待实施*