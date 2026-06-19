# data_service.py Handler 域拆分计划

> **Status:** Draft | **依赖:** P0-2 已完成（notification.py 模式验证）

**Goal:** 将 `src/data_service.py`（3121 行，58 个 `_handle_*` 方法挤在一个 `DataService` 类里）按业务域拆分为 `src/handlers/` 子模块，每个 ≤400 行。保持对外契约（`_actions` dict → handler 映射）不变。

---

## 现状审计（2026-06-19）

```
src/data_service.py  3121 行
  class DataServiceError / BadRequestError / ...     L32-118  (88 行)  — 可独立
  class DataService:                                 L120-3119 (~3000 行)
    __init__ / hello / refresh / quit               L120-330
    _handle_analyze                                  L414-556   (143)
    _handle_deep_analyze                             L557-708   (152)
    _handle_analyze_stream                           L709-949   (241)
    _handle_get_history                              L950-1006  (57)
    _handle_search_news                              L1007-1040 (34)
    _handle_get_kline_data                           L1041-1077 (37)
    _handle_get_indicators                           L1078-1150 (73)
    _handle_get_drawing_data                         L1151-1192 (42)
    _handle_get_tasks/_get_task/_cancel_task         L1193-1240 (48)
    _handle_add_position                             L1241-1276 (36)
    _handle_remove_position                          L1277-1294 (18)
    _handle_update_position                          L1295-1324 (30)
    _handle_get_positions                            L1325-1345 (21)
    _handle_get_institutional                        L1346-1360 (15)
    _handle_get_dragon_board                         L1361-1373 (13)
    _handle_run_backtest                             L1374-1459 (86)
    _handle_get/save/delete/toggle_alert             L1460-1529 (70)
    _handle_screen_stocks                            L1530-1635 (106)
    _handle_get_financials                           L1636-1735 (100)
    _handle_get_key_metrics                          L1736-1758 (23)
    _handle_get_market_overview                      L1759-1789 (31)
    _handle_get_market_review                        L1790-1869 (80)
    _handle_get_market_reviews_history               L1870-1963 (94)
    _handle_optimize_strategy                        L1964-2002 (39)
    _handle_list_plugins                             L2003-2014 (12)
    _handle_get_plugin_info                          L2015-2081 (67)
    _handle_export_strategy                          L2082-2113 (32)
    _handle_import_strategy                          L2114-2151 (38)
    _handle_list_strategies                          L2152-2179 (28)
    _handle_delete_strategy                          L2180-2196 (17)
    _handle_list_providers                           L2197-2215 (19)
    _handle_get/set_theme                            L2216-2237 (22)
    _handle_get/set_languages                        L2238-2259 (22)
    _handle_get/update_config                        L2260-2366 (107)
    _handle_search_knowledge                         L2367-2393 (27)
    _handle_get_factor_value                         L2394-2418 (25)
    _handle_analyze_factor_ic                        L2419-2454 (36)
    _handle_get_factor_rankings                      L2455-2489 (35)
    _handle_research                                 L2490-2542 (53)
    _build_demo_* / demo 辅助函数                   L575-700, L2544-2800 (散布)
    WebSocket server 逻辑                            L2800-3119 (319)
  + 58 项 _actions dict                              L74-135

总计：~3000 行业务逻辑 + 58 个 handler
```

## 目标架构

```
src/
├── data_service.py          # DataService 骨架（~200 行）
│                              — DataServiceError 系列异常类
│                              — DataService.__init__ + _handle_request dispatch
│                              — _actions dict（委托到 handlers/ 模块）
│                              — Demo 数据构建辅助（保持向后兼容）
│
├── handlers/                # 新建：按域拆分的 handler 模块
│   ├── __init__.py
│   ├── core.py              # hello / refresh / quit（~60 行）
│   ├── markets.py           # get_markets / get_history / get_kline_data /
│   │                          get_indicators / get_drawing_data（~270 行）
│   ├── analysis.py          # analyze / analyze_stream / deep_analyze / research（~600 行）
│   ├── portfolio.py         # add/remove/update/get_position（~120 行）
│   ├── sim.py               # sim_buy/sell/summary/history/reset（~80 行）
│   ├── backtest.py          # run_backtest（~90 行）
│   ├── alerts.py            # get/save/delete/toggle_alert（~75 行）
│   ├── screen.py            # screen_stocks（~110 行）
│   ├── financials.py        # get_financials / get_key_metrics（~130 行）
│   ├── market_review.py     # get_market_overview/review/reviews_history（~210 行）
│   ├── strategies.py        # list/export/import/delete/optimize_strategy（~160 行）
│   ├── plugins.py           # list_plugins / get_plugin_info / list_providers（~100 行）
│   ├── config.py            # get/set_theme, get/set_language, get/update_config（~140 行）
│   ├── search.py            # search_news / search_knowledge（~70 行）
│   ├── factors.py           # get_factor_value / analyze_factor_ic / get_factor_rankings（~100 行）
│   └── institutional.py     # get_institutional / get_dragon_board（~40 行）
│
└── ws/                      # WebSocket 逻辑（已有 ws_client.py，可扩展）
    └── server.py            # DataService 内的 WS server 逻辑（~320 行）

tests/
└── test_handlers/            # 按 handler 模块对应的测试（从 test_data_service.py 拆分）
```

## 实施步骤

### Phase 1：建立注册机制（最底层，1 次改动）

- [ ] 1.1 在 `src/handlers/__init__.py` 中定义 `def register_all(service: DataService) -> None` 函数
  - 从各子模块 import `register(service)` 并调用
  - 每个子模块的 `register()` 把 handler 注入 `service._actions` dict
- [ ] 1.2 `DataService.__init__` 中把 `self._actions = {}` 然后 `register_all(self)`
- [ ] 1.3 跑全套测试 — **此步必须 1153+ passed**（注册机制本身不改变行为）

### Phase 2：逐域搬迁（每个 handler domain 单独 commit）

每个 domain 搬迁的节奏：
1. 在对应 `src/handlers/<domain>.py` 中创建 `register(service)` 函数 + 静态 handler 函数
2. 从 `data_service.py` 中删除对应 `_handle_*` 方法和 `_actions` 条目
3. 运行全套测试

搬迁顺序（按依赖从低到高）：

- [ ] 2.1 `handlers/core.py` — hello / refresh / quit（最简，热身）
- [ ] 2.2 `handlers/config.py` — theme / language / config（几乎无外部依赖）
- [ ] 2.3 `handlers/plugins.py` — list_plugins / get_plugin_info / list_providers
- [ ] 2.4 `handlers/alerts.py` — 4 alert handlers
- [ ] 2.5 `handlers/portfolio.py` — 4 position handlers
- [ ] 2.6 `handlers/sim.py` — 5 sim handlers
- [ ] 2.7 `handlers/institutional.py` — 2 handlers
- [ ] 2.8 `handlers/markets.py` — 5 market data handlers
- [ ] 2.9 `handlers/backtest.py` — 1 handler
- [ ] 2.10 `handlers/financials.py` — 2 handlers
- [ ] 2.11 `handlers/screen.py` — 1 handler
- [ ] 2.12 `handlers/strategies.py` — 5 strategy handlers
- [ ] 2.13 `handlers/search.py` — search_news / search_knowledge
- [ ] 2.14 `handlers/factors.py` — 3 factor handlers
- [ ] 2.15 `handlers/market_review.py` — 3 market review handlers
- [ ] 2.16 `handlers/analysis.py` — analyze / deep_analyze / analyze_stream / research（最大块，最后搬）

### Phase 3：WebSocket 分离

- [ ] 3.1 把 WS server 逻辑（~320 行）迁到 `src/ws/server.py`
- [ ] 3.2 DataService 只保留 WS entry point 委托

### Phase 4：测试拆分（可选）

- [ ] 4.1 `tests/test_handlers/` 按 domain 拆分（从 `test_data_service.py` 的 ~50 个测试类中提取）

---

## 决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| Handler 注册方式 | 每 domain 的 `register(service)` 显式注入 `_actions` dict | 保持显式可 grep，不依赖装饰器/反射魔法 |
| Handler 签名 | `def handler(service: DataService, req: Dict) -> Dict`（静态函数） | 去掉 `self` 依赖，各 handler 通过显式参数获取依赖 |
| Demo 数据 | 保留在 `data_service.py` 内（`_build_demo_*` 辅助函数） | 约 300 行，域边界清晰，不值得拆 |
| 测试文件 | 搬迁期间不拆——保留传统 `test_data_service.py` 保证回归 | 避免同时改测试结构引入噪音；Phase 4 可做 |

---

## 风险

| 风险 | 缓解 |
|---|---|
| Handler 间有隐藏的 `self._xxx` 状态依赖 | Phase 1 时全面审计 handler 内部引用。频繁引用的共享状态（config / db / task dict）通过 `service` 参数显式访问 |
| `_handle_analyze` 等复杂 handler 内部调用 `self._send_notification()` 等辅助方法 | 辅助方法暂时保留在 DataService 上，handler 通过 `service._send_notification()` 调用；后续再拆 |
| WebSocket 逻辑与 handler 耦合 | Phase 3 独立处理，先拆 handler 再拆 WS |

---

## 完成标准

- [ ] `src/data_service.py` ≤ 500 行（DataService 骨架 + demo + WS entry）
- [ ] 58 个 handler 全部在 `src/handlers/` 下，每个模块 ≤ 400 行
- [ ] `_actions` dict 由 `register_all()` 组装
- [ ] `pytest -q` ≥ 1153 passed / 0 failed
- [ ] `grep "_handle_" src/data_service.py` 返回 0

---

*起草: 2026-06-19*
