# search_service.py 迁移收尾计划

> **接续：** [2026-05-09-search-modularization.md](./2026-05-09-search-modularization.md) — 只完成了 `src/search_pkg/` 脚手架（base/bocha/tavily/serpapi/manager 框架），旧 `src/search_service.py` 未删，生产代码未切。

**目标：** 608 行 → 163 行（同样模式，保留 shim，下一个迭代再删除）。

## 现状（2026-06-20 审计）

### 生产 import 方（6 处）
```
src/data_service.py        SearchService ⇒ search_stock_news
src/market_analyzer.py      SearchService ⇒ search_stock_news（做 news 分析）
src/core/pipeline.py        SearchService ⇒ is_available / search_comprehensive_intel / format_intel_report
src/core/market_review.py   SearchService（类型注解）
src/agents/research_agent.py  get_search_service ⇒ 全局单例
```

### 旧 SearchService 公共方法（3 个在用以外的都可 dead）
```
✓ search_stock_news               — 2 调用方（data_service + market_analyzer）
✓ search_comprehensive_intel      — 1 调用方（pipeline）
✓ format_intel_report             — 1 调用方（pipeline）
✓ is_available                    — 1 调用方（pipeline）
✓ get_search_service              — 1 调用方（research_agent）

✗ search_stock_events             — 仅内部调用（dead）
✗ batch_search                    — 无人调用（dead）
✗ search_stock_price_fallback     — 仅 search_stock_with_enhanced_fallback 调（dead）
✗ search_stock_with_enhanced_fallback — 无人调用
✗ format_price_search_context     — 无人调用
```

`SearchService` 核心引擎部分（~350 行）已经迁移到 `SearchManager.executor_with_providers` 的等效逻辑中。

### 缺失的关键能力
- `SearchManager` 缺少 `search_comprehensive_intel()` 和 `format_intel_report()` — pipeline.py 用
- 缺少 `get_search_service()` 单例 — research_agent 用

### 阻塞点
`search_comprehensive_intel()` 是一个包含 7 个子搜索的**并发编排**方法（股票代码变动/高管增减/板块轮动/资金动向/热度/评级/南向资金）。应迁移到 `SearchManager` 而不是留在 shim 层。

## 迁移方案

只迁 4 个有外部调用者的方法到 `search_pkg/manager.py`：
- `search_stock_news` — 已有（`manager.py:150`），对齐返回格式
- `search_comprehensive_intel` — 新增到 `manager.py`
- `format_intel_report` — 新增到 `manager.py` 或 `search_pkg/intel_formatter.py`
- `get_search_service` — 新增到 `search_pkg/singletons.py`

**死代码（不复刻，不迁移，仅记录）**：`search_stock_events`, `batch_search`, `search_stock_price_fallback`, `search_stock_with_enhanced_fallback`, `format_price_search_context`。

## 开始执行

无需等审批。直接推 `refactor/search-service-migration-finish` 分支，逐步骤提交。

---

*2026-06-20 — 规划即执行*