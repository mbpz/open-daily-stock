# analyzer.py 模块化拆分计划

> **Status:** Draft | **依赖:** P0-2 已完成（notification.py 模式验证）

**Goal:** 将 `src/analyzer.py`（2246 行）拆分，核心 `GeminiAnalyzer` 类（~1860 行）按职责分离为 prompt 构建、API 调用、流式处理、响应解析四个独立模块。

---

## 现状审计（2026-06-19）

```
src/analyzer.py  2246 行
  class AnalysisResult            L182-324   (143 行)  ← 可独立为 types.py
  class DeepAnalysisResult        L325-384   (60 行)    ← 可独立为 types.py
  class GeminiAnalyzer            L385-2238  (1854 行) ← 核心问题
    __init__ / _init_openai_fallback / _init_model      L580-741   (162)
    _call_openai_api / _call_api_with_retry             L746-915   (170)
    analyze (非流式)                                     L916-1074  (159)
    _call_gemini_stream / _call_openai_stream            L1075-1205 (131)
    analyze_stream (流式)                                 L1206-1348 (143)
    _format_prompt                                       L1349-1529 (181)
    _format_volume / _format_amount                      L1530-1551 (22)
    _parse_response / _fix_json_string / _parse_text      L1552-1697 (146)
    batch_analyze                                        L1698-1730 (33)
    deep_analyze + _build_specialist_prompts +           L1731-2129 (399)
      _format_technical/fundamental/news_prompt +
      _run_specialist + _parse_specialist_json +
      _synthesize + _synthesize_fallback
    is_available / _switch_to_fallback_model             L717-745   (29)
  class OrchestratorCancelled    L2239-2246 (8 行)
```

**职责混在一起**：
- LLM API 调用（重试、stream、fallback）与 prompt 构建混在一个类
- Multi-agent 编排（deep_analyze）与单次 analyze 混在一个类
- Markdown 解析（`_fix_json_string`、`_parse_text_response`）散落在 3 个方法

## 目标架构

```
src/
├── analyzer.py                  # ~80 行 — 向后兼容 shim（re-export 新模块）
│
├── llm/                         # 新建：LLM 调用层
│   ├── __init__.py
│   ├── types.py                 # AnalysisResult / DeepAnalysisResult（~220 行）
│   ├── client.py                # LLM client：init / is_available / fallback（~180 行）
│   ├── api.py                   # _call_openai_api / _call_api_with_retry（~170 行）
│   ├── streaming.py             # _call_gemini_stream / _call_openai_stream（~135 行）
│   └── prompts.py               # _format_prompt / _format_volume / _format_amount（~210 行）
│
├── agents/                       # 已有，需增强
│   └── (现有 6 个 agent 不变)
│
├── llm/parsing.py               # _parse_response / _fix_json_string /
│                                  _parse_text_response / _parse_specialist_json（~170 行）
│
└── llm/orchestrator.py          # deep_analyze / batch_analyze /
                                   _build_specialist_prompts / _run_specialist /
                                   _synthesize（~450 行）
```

## 实施步骤

### Phase 1：抽类型 + 客户端骨架

- [ ] 1.1 把 `AnalysisResult` + `DeepAnalysisResult` + `OrchestratorCancelled` 迁到 `src/llm/types.py`
- [ ] 1.2 在 `src/llm/client.py` 中实现 `LLMClient` 类
  - `__init__` / `_init_openai_fallback` / `_init_model` / `is_available` / `_switch_to_fallback_model`
  - 纯配置 + 连接管理，不涉及任何调用逻辑
- [ ] 1.3 `GeminiAnalyzer` 内部委托到 `LLMClient`
- [ ] 1.4 跑全套测试 — **必须 1153+ passed**

### Phase 2：拆 API 调用层

- [ ] 2.1 把 `_call_openai_api` + `_call_api_with_retry` 迁到 `src/llm/api.py`
- [ ] 2.2 `GeminiAnalyzer.analyze()` 通过 `api.call(…)` 委托
- [ ] 2.3 跑全套测试

### Phase 3：拆流式处理

- [ ] 3.1 把 `_call_gemini_stream` + `_call_openai_stream` + `analyze_stream` 迁到 `src/llm/streaming.py`
- [ ] 3.2 跑全套测试

### Phase 4：拆 Prompt 构建

- [ ] 4.1 把 `_format_prompt` / `_format_volume` / `_format_amount` 迁到 `src/llm/prompts.py`
- [ ] 4.2 跑全套测试

### Phase 5：拆响应解析

- [ ] 5.1 把 `_parse_response` / `_fix_json_string` / `_parse_text_response` / `_parse_specialist_json` 迁到 `src/llm/parsing.py`
- [ ] 5.2 跑全套测试

### Phase 6：拆多 Agent 编排

- [ ] 6.1 把 `deep_analyze` / `batch_analyze` / `_build_specialist_prompts` / `_run_specialist` / `_synthesize` 迁到 `src/llm/orchestrator.py`
- [ ] 6.2 跑全套测试

### Phase 7：Shim + 清理

- [ ] 7.1 `src/analyzer.py` → 退化 re-export shim（~20 行）
- [ ] 7.2 切所有调用方：`from src.analyzer import GeminiAnalyzer` → `from src.llm import LLMAnalyzer`（或保留旧路径）
- [ ] 7.3 跑全套测试

---

## 决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 模块命名 | `src/llm/`（不是 `src/analyzer_modules/`） | 短、语义清晰、可扩展（未来加 Claude/Ollama 时加子模块） |
| GeminiAnalyzer 名称 | 迁后不重命名，保持 `GeminiAnalyzer` 为 facade | 避免影响所有调用方（MCP tools / TUI / GUI / agent 代码大量引用此名） |
| 旧 analyzer.py | Phase 7 退化为 shim（同 notification.py 模式） | 已验证的模式；零风险 |
| 测试 | 不拆测试文件——保持 `test_analyzer.py` 测试整体行为 | 避免同时动测试引入噪音 |

---

## 风险

| 风险 | 缓解 |
|---|---|
| `analyze()` 和 `analyze_stream()` 内联了大量 config/state 读写 | Phase 2/3 用显式参数传依赖，不引入隐式闭包 |
| `deep_analyze` 与 `src/agents/orchestrator.py` 职责重叠 | Phase 6 时评估是否合并或明确边界 |

---

## 完成标准

- [ ] `src/analyzer.py` ≤ 80 行（shim）
- [ ] `src/llm/` 7 个模块，每个 ≤ 500 行
- [ ] `pytest -q` ≥ 1153 passed / 0 failed
- [ ] 对外契约不变：`from src.analyzer import GeminiAnalyzer, AnalysisResult` 仍可用

---

*起草: 2026-06-19*
