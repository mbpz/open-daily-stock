# ADR-002: stdio JSON IPC 机制

**状态:** 已接受
**日期:** 2026-05-10

---

## 背景

open-daily-stock 采用双进程架构：
- 主进程 (main.py) 管理 TUI/GUI 生命周期
- 子进程 (DataService) 作为后端守护进程

TUI/GUI 客户端需要与 DataService 通信，需要一种可靠的进程间通信机制。

## 决策

使用 **stdio JSON** 作为 TUI/GUI 与 DataService 之间的 IPC 机制。

### 协议设计

```json
// 请求 (客户端 → DataService)
{"action": "get_markets", "id": 1, "params": {}}

// 响应 (DataService → 客户端)
{"id": 1, "result": {...}, "error": null}

// 推送 (DataService → 客户端，实时数据)
{"action": "push", "data": {"type": "markets", "values": [...]}}
```

### 选择理由

1. **实现简单** — 无需网络编程或 Unix Domain Socket
2. **调试友好** — stdin/stdout 可直接重定向，日志清晰
3. **跨平台** — 所有操作系统都支持 stdio
4. **Textual/Flet 兼容** — 两个框架都支持 subprocess stdin/stdout

### 实施

```python
# data_service.py
import json, sys
from threading import Thread

def handle_request(req: dict):
    action = req.get("action")
    if action == "get_markets":
        return get_markets(req.get("params", {}))

def main():
    for line in sys.stdin:
        req = json.loads(line)
        resp = handle_request(req)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
```

---

## 后果

**正面：**
- 实现简洁，代码量少
- 易于测试（echo '{"action":"hello"}' | python data_service.py）
- 无网络依赖，隐私安全

**负面：**
- 单向通信，无法双向推送（已规划 WebSocket 替代方案 P3-9）
- readline 阻塞，不支持复杂交互
- 不支持多客户端同时连接

**改进计划：**
- P3-9: WebSocket IPC 模式 — 保留 stdio 兼容，新增 WebSocket 支持双向异步通信
