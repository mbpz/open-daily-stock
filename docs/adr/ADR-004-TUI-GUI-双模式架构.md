# ADR-004: TUI+GUI 双模式架构

**状态:** 已接受
**日期:** 2026-05-10

---

## 背景

open-daily-stock 的目标用户包含两类：
- **技术用户** — 习惯命令行，熟悉终端操作
- **普通用户** — 偏好图形界面，点击操作

单一界面无法同时满足两类用户需求。

## 决策

采用 **TUI + GUI 双入口，单后端** 架构：

```
                    main.py (唯一入口)
                         │
            ┌────────────┴────────────┐
            ↓                         ↓
      --tui 模式                  --gui 模式
            │                         │
     Textual App                  Flet App
            │                         │
            └────────────┬────────────┘
                         │
                  stdio JSON
                         │
                         ↓
              DataService (后端守护进程)
              (统一数据处理 + AI 分析)
```

### 选择理由

1. **用户覆盖最大化** — 技术用户用 TUI，普通用户用 GUI
2. **代码复用** — 共享 DataService 后端，避免重复实现
3. **一致性** — 两个界面功能完全对等
4. **无竞品对标** — 市场上无其他开源股票工具同时提供 TUI+GUI

### 实施

```python
# main.py
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--tui", action="store_true")
parser.add_argument("--gui", action="store_true")
args = parser.parse_args()

if args.tui:
    from tui.app import run
elif args.gui:
    from gui.main import run
else:
    # 默认 GUI
    from gui.main import run
```

---

## 后果

**正面：**
- 用户根据习惯选择界面，门槛低
- 技术用户可展示 TUI 操作能力，利于传播
- 同一代码库维护两套界面，效率高

**负面：**
- 双界面开发工作量约 1.5x
- 需要保持功能对等

**竞品对比：**

| 产品 | TUI | GUI | 双模式 |
|------|:---:|:---:|:------:|
| open-daily-stock | ✅ | ✅ | ✅ |
| 富途牛牛 | ❌ | ✅ | ❌ |
| 同花顺 | ✅ (传统) | ✅ | ❌ |
| TradingView | ❌ | ✅ | ❌ |
| Backtrader | ✅ | ❌ | ❌ |

**技术差异点：**
- open-daily-stock 使用现代 TUI 框架 (Textual)，而非传统 ncurses
- open-daily-stock GUI 使用 Flet (Flutter)，而非 Electron
