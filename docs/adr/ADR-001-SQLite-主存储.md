# ADR-001: SQLite 作为主存储

**状态:** 已接受
**日期:** 2026-05-10

---

## 背景

open-daily-stock 需要在本地持久化存储多种数据：
- 自选股列表
- 持仓记录（成本、盈亏）
- K线历史数据（用于回放）
- 分析任务状态
- 用户配置

## 决策

使用 **SQLite** 作为单一数据存储引擎，通过 SQLAlchemy ORM 暴露接口。

### 选择理由

1. **本地优先** — 无服务器依赖，数据存在用户本地
2. **零配置** — 无需安装数据库服务，打开文件即可用
3. **并发安全** — SQLite 支持 WAL 模式，支持多进程读写
4. **可移植** — 单一 .db 文件，方便备份和迁移
5. **足够轻量** — 对于个人工具，数据量不超过 100MB

### 实施

```python
# storage.py
from sqlalchemy import create_engine
engine = create_engine("sqlite:///open-daily-stock.db", connect_args={"check_same_thread": False})

# WAL 模式提升并发性能
engine.execute("PRAGMA journal_mode=WAL")
```

### Schema 设计

| 表 | 用途 |
|---|---|
| `stocks` | 自选股列表 |
| `positions` | 持仓记录 |
| `market_history` | K线历史 |
| `tasks` | 分析任务 |

---

## 后果

**正面：**
- 用户无感知数据库安装
- 数据完全归用户所有
- 单文件备份简单

**负面：**
- 多进程并发写入需通过 DataService 中转（TUI/GUI 不直接写库）
- 不适合多用户场景（不是我们的目标）

**替代方案考虑：**
- PostgreSQL: 需要安装服务，不符合本地优先
- DuckDB: 分析友好但生态不如 SQLite
- JSON 文件: 无法支持复杂查询
