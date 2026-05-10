# P5 Roadmap: 2026 生态演进增强

**日期:** 2026-05-10
**状态:** Draft
**研究来源:** 3 个并行 agent（GitHub 竞品、AI/LLM 模式、UX/分发策略）

---

## 一、核心发现

2025-2026 年出现了三个范式转移：

1. **MCP 成为 AI Agent 通用接口** — 10+ 个项目已将金融数据封装为 MCP Server
2. **多 Agent 辩论取代单 LLM 分析** — TradingAgents-AShare (15 agents)、FinRobot 等已验证
3. **因子分析 + AI 是新的量化前沿** — FactorHub (338⭐)、AlphaGPT (1992⭐)、akquant (1114⭐)

---

## 二、P5 任务

### P5-1: Streaming LLM 响应（优先级: 最高）
**来源:** AI Agent · **工作量:** 低 · **影响:** 高

- Gemini/OpenAI 响应 token-by-token 流式输出到 TUI/GUI
- 感知延迟从 ~8s 降至 ~1s
- 复用现有 WebSocket IPC (P3-9)

### P5-2: MCP Server Bridge（优先级: 最高）
**来源:** GitHub Agent · **工作量:** 中 · **影响:** 极重要

- 将 26 个 DataService action 包装为 MCP Tool
- DataService 启动 MCP server 模式（stdio JSON = MCP 兼容）
- 让 Claude/Cursor/Windsurf 等 AI Agent 直接调用行情/分析/回测

### P5-3: Deep Analysis 多 Agent 模式（优先级: 高）
**来源:** AI Agent + GitHub Agent · **工作量:** 中高 · **影响:** 高

- 3 个并行 Agent：技术面/基本面/新闻舆情
- 第 4 个合成 Agent 汇总结果
- 单次分析保留为默认，Deep Analysis 可选（Ctrl+D）

### P5-4: Homebrew + winget 分发（优先级: 高）
**来源:** UX Agent · **工作量:** 低 · **影响:** 高

- Homebrew formula: `brew install mbpz/tap/open-daily-stock`
- winget manifest: `winget install open-daily-stock`
- ~50 行配置即可触达 10x 用户

### P5-5: Demo Data 免配置体验（优先级: 高）
**来源:** UX Agent · **工作量:** 低 · **影响:** 中高

- 首次启动提供 "试用示例数据" 模式
- 预置 5 只热门股的昨日快照 + AI 分析样例
- 免 API key 即可看到产品价值

### P5-6: RAG 知识库（优先级: 中）
**来源:** AI Agent · **工作量:** 中 · **影响:** 中

- SQLite FTS5 全文索引历史分析结果
- 新分析时注入相关历史上下文
- 价值随时间累积增长

### P5-7: Command Palette 命令面板（优先级: 中）
**来源:** UX Agent · **工作量:** 中 · **影响:** 中

- Ctrl+K 模糊搜索所有 26 个 DataService action
- 统一 TUI/GUI 操作入口
- 2025-2026 桌面应用 #1 UX 模式

### P5-8: In-App 通知中心（优先级: 中低）
**来源:** UX Agent · **工作量:** 中 · **影响:** 中低

- 本地 Toast 通知 + 通知历史面板
- "600519 跌 3.2%"、"AI 分析完成"
- 增加日活回访

### P5-9: Agentic Research Mode（优先级: 低）
**来源:** AI Agent · **工作量:** 高 · **影响:** 高

- LLM 自主决定调用哪些 DataService action 做研究
- 工具调用循环，最多 10 步
- 风险：agent 循环不可预测

### P5-10: 因子分析引擎（优先级: 低）
**来源:** GitHub Agent · **工作量:** 高 · **影响:** 中

- Alpha 发现、IC/IR 分析、因子衰减监控
- 替代纯技术指标分析

---

## 三、优先级矩阵

```
        高影响
          │
  P5-1   │  P5-3        P5-9
  P5-2   │  P5-4
  P5-5   │
         │  P5-6   P5-7
  P5-8   │
─────────┼─────────────────────
         │              P5-10
         │
         低影响
          │←──────────────────→
         低难度              高难度
```

**建议第一阶段 (立即):** P5-1 + P5-2 + P5-4 + P5-5（4项低工作量高影响）

---

## 四、非目标

- ❌ 不做 Docker 部署（与本地优先定位矛盾）
- ❌ 不做 Pine Script 兼容（维护成本过高）
- ❌ 不做 Rust 性能层（日线数据 Python 足够）
- ❌ 不做直播券商 API（法律风险）

---

*最后更新: 2026-05-10*
