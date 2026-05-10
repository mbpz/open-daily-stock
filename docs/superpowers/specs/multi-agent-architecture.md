# Multi-Agent Architecture Design

**Date**: 2026-05-10
**Status**: Draft
**Source**: Competitive analysis of crewai_stock, llm-stock-team-analyzer, QuantScope, daily_stock_analysis

---

## 一、动机

当前 open-daily-stock 的 AI 分析是**单一 LLM 调用**：用户选择股票 → 获取行情+基本面数据 → 构造 prompt → 一次性返回分析结果。

问题：
1. 分析深度受限于单次 prompt 上下文窗口
2. 无法交叉验证（技术面信号 vs 基本面信号 可能矛盾）
3. 缺乏分工（同一模型既看图表又读财报又扫新闻）
4. 无法进行"反思"（分析结论无自检机制）

竞品已经在多 Agent 方向验证了价值：
- **llm-stock-team-analyzer**: LangGraph 4-Agent (技术×2 + 研究 + 交易) + Reflection 节点
- **crewai_stock**: CrewAI Flow 多 Agent 协作
- **QuantScope**: 多 Agent + Quality Gates
- **daily_stock_analysis**: Orchestrator + Executor + Skills + Tools

---

## 二、目标架构

### 2.1 Agent 拓扑 (LangGraph StateGraph)

```
                    ┌─────────────┐
                    │   Trigger   │ (用户请求分析 "000001")
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Dispatcher │ (路由节点: 判断分析需求)
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
   │  Technical  │  │ Fundamental │  │    News     │
   │   Analyst   │  │   Analyst   │  │   Analyst   │
   │ (技术面Agent)│  │ (基本面Agent)│  │ (新闻Agent) │
   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Synthesizer│ (合成Agent: 交叉验证 + 矛盾检测)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Reflection │ (自检: 置信度校准 + 逻辑一致性)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Output    │ (决策仪表盘 + 风险提示)
                    └─────────────┘
```

### 2.2 Agent 定义

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **Technical Analyst** | K线形态、技术指标、量价关系 | OHLCV 历史 + 指标计算结果 | 技术面评分 (1-10) + 信号列表 |
| **Fundamental Analyst** | 财务指标、估值分析 | 三表 + 关键指标 (PE/PB/ROE...) | 基本面评分 + 估值判断 |
| **News Analyst** | 新闻情绪、事件影响 | 搜索新闻 + 公告 | 情绪评分 (-1~1) + 关键事件 |
| **Synthesizer** | 交叉验证、矛盾检测 | 3 个 Agent 的输出 | 综合评分 + 矛盾点列表 |
| **Reflection** | 置信度校准、逻辑自检 | Synthesizer 输出 | 校准后结论 + 不确定性标注 |

### 2.3 LangGraph State Schema

```python
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END

class AnalysisState(TypedDict):
    # Input
    symbol: str
    market: str  # "A" | "HK" | "US"
    request_type: str  # "quick" | "deep" | "screening"

    # Per-agent outputs
    technical_score: Optional[float]
    technical_signals: List[str]
    technical_confidence: Optional[float]

    fundamental_score: Optional[float]
    fundamental_signals: List[str]
    fundamental_confidence: Optional[float]

    news_score: Optional[float]
    news_signals: List[str]
    news_confidence: Optional[float]

    # Synthesis
    composite_score: Optional[float]
    contradictions: List[str]  # 矛盾检测结果
    recommendation: Optional[str]  # buy/hold/sell

    # Reflection
    calibrated_score: Optional[float]
    uncertainty_flags: List[str]
    final_verdict: Optional[str]
```

---

## 三、与现有架构的集成

### 3.1 渐进式替换

```
Phase 1 (P6-2 本期):  新增 Agent graph 作为 analyzer.py 的替代引擎
                         DataService action: analyze_v2 (并发运行)
                         默认保留 analyze (旧单Agent)

Phase 2 (下期):         analyze_v2 成为默认
                         analyze 标记 deprecated
                         旧分析结果页支持 Agent 输出渲染

Phase 3 (远期):         移除旧 analyze
```

### 3.2 DataService 集成

```python
# src/data_service.py
async def handle_analyze_v2(self, params):
    """多 Agent 分析 (流式)"""
    state = AnalysisState(
        symbol=params["symbol"],
        market=params.get("market", "A"),
        request_type=params.get("request_type", "quick"),
    )
    graph = build_analysis_graph()
    async for event in graph.astream(state):
        yield event  # 每个节点完成时推送
```

### 3.3 流式 UI 适配

```
TUI: Textual 进度条 + 每 Agent 完成更新
GUI: Flet Column 动态添加 Agent 结果卡片
     每个 Agent 完成 → 卡片出现 → Synthesizer → 结论区闪烁
```

---

## 四、关键技术决策

### 4.1 为什么选 LangGraph 而不是 CrewAI？

| 维度 | LangGraph | CrewAI |
|------|-----------|--------|
| 状态管理 | ✅ TypedDict StateGraph | ❌ 隐式共享上下文 |
| 流式支持 | ✅ astream() 原生 | 弱 |
| 条件路由 | ✅ conditional_edges | ✅ 基础 |
| 反思循环 | ✅ 原生循环边 | 弱 (需手动) |
| 生态 | LangChain 集成 | 独立生态 |
| 复杂度 | 中等 | 低 |
| 与现有架构匹配 | ✅ 也使用 TypedDict/流式 | ❌ 黑盒 Flow |

**决策**: LangGraph，因为 (1) 流式原生支持匹配 P5-1, (2) StateGraph 透明可调试, (3) 反思循环是竞品验证的关键模式

### 4.2 为什么 4 Agent 而非 3 或 5？

- **3 不足**: 缺少合成层，3 个独立输出需要人工解读
- **5 过多**: 当前阶段增加复杂度但边际收益递减
- **4 刚好**: 3 个专业 Agent + 1 个合成 Agent (Reflection 作为节点而非独立 Agent)

参考 llm-stock-team-analyzer 的 4-Agent 验证模式。

### 4.3 Agent 间通信

```
不采用: Agent ↔ Agent 直接通信 (复杂度 O(n²))
采用:  Shared State (TypedDict) → 下一节点读取上一节点输出
优势:  可追踪、可回放、可调试
```

---

## 五、实现计划

### P6-2: 多 Agent 分析架构 (5 天)

**Day 1-2: LangGraph 基础设施**
- 安装 langgraph + langchain
- State schema 定义
- 3 个 Analyst Agent prompt 模板
- 基础 graph 搭建 (无循环)

**Day 3: 合成 + 反思**
- Synthesizer prompt (矛盾检测)
- Reflection node (置信度校准)
- 条件边: 置信度 < 阈值 → 重新分析

**Day 4: DataService 集成**
- `analyze_v2` action
- 流式事件推送
- 与现有 `analyze` action 并行

**Day 5: UI 适配 + 测试**
- TUI Agent 进度展示
- GUI Agent 结果卡片
- 集成测试 (完整 flow)

### 测试策略
- 单 Agent 单元测试 (mock LLM 响应)
- Graph 结构测试 (状态转换正确性)
- 流式输出测试 (事件顺序)
- 端到端: 分析 000001 → 验证输出 schema

---

## 六、参考竞品实现

| 项目 | Agent 拓扑 | 亮点 | 可复用 |
|------|-----------|------|--------|
| [llm-stock-team-analyzer](https://github.com/jason8745/llm-stock-team-analyzer) | 4 Agent + Reflection | LangGraph StateGraph, 清晰的状态流 | StateGraph 结构参考 |
| [QuantScope](https://github.com/Kai-dev7/QuantScope) | Multi-Agent + Quality Gates | Quality Gates 门禁机制 | Quality check 概念 |
| [crewai_stock](https://github.com/liangdabiao/crewai_stock_analysis_system) | CrewAI Flow | 任务分解 + 协作流程 | Prompt 模板参考 |
| [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | Orchestrator + Skills | Agent 工具系统 + 策略注册 | Skills 注册模式 |

---

## 七、风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 延迟叠加 (4 次调用) | 3 个 Analyst 并行调用, 仅 Synthesizer 串行 |
| Token 成本过高 | "quick" 模式跳过 Reflection，"deep" 模式全流程 |
| Agent 输出格式不稳定 | Pydantic schema 约束 + retry on parse error |
| 矛盾检测误判 | 只标注矛盾，不强制裁决，最终由用户判断 |
