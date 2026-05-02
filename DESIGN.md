# open-daily-stock 设计文档

---

## 一、项目定位

**本地 PC 端 TUI + GUI 双模式应用**。用户下载打包好的可执行文件，双击运行即可使用所有功能，无需安装 Python、无需配置服务端。

**核心场景：** 用户在本地终端或图形界面查看自选股行情、手动触发股票分析、配置通知渠道。

---

## 二、设计原则

### 2.1 极简依赖
- 只依赖 Python 标准库 + PyInstaller
- 数据来源：AkShare（免费 A 股数据）、YFinance（港美股）
- AI 分析：用户自己的 API Key（Gemini/OpenAI 兼容）

### 2.2 本地优先
- 所有数据本地存储（SQLite）
- 不需要任何服务端
- 网络只用于：拉取行情数据、拉取 AI 分析结果、推送通知到用户配置的 Webhook

### 2.3 双模式对等
- TUI 和 GUI 功能完全对等，共享同一后端
- 用户可选使用终端（TUI）或图形界面（GUI）

### 2.4 单一职责
- 界面层只负责交互（展示、输入、导航）
- DataService 后端负责数据拉取、缓存、推送
- 业务逻辑在 src/（可被 main.py CLI 复用）

---

## 三、架构设计

### 3.1 分层结构

```
┌─────────────────────────────────────────────────┐
│           界面层（交互）                          │
│  TUI (Textual)    GUI (Flet)                   │
└──────────┬──────────────────┬──────────────────┘
           │    stdio JSON     │
┌──────────┴──────────────────┴──────────────────┐
│           DataService (后端守护进程)            │
│  - 数据拉取 (AkShare/YFinance)                │
│  - 缓存管理 (SQLite)                           │
│  - 定时推送 (30s)                              │
│  - AI 分析 (Gemini/DeepSeek)                   │
└──────────┬──────────────────┬──────────────────┘
           │                  │
┌──────────┴──────────────────┴──────────────────┐
│           数据层                                │
│  data_provider/ · SQLite                       │
└────────────────────────────────────────────────┘
```

### 3.2 进程模型

```
main.py (唯一入口)
    ↓
fork() → DataService 子进程
    ↓
    ├── stdin: 接收客户端请求 (JSON)
    ├── stdout: 发送响应/推送数据 (JSON)
    └── SQLite: 数据持久化

TUI/GUI 客户端
    ↓
    └── stdin/stdout 连接 DataService
```

**进程启动流程：**
1. 用户运行 `main.py`
2. main.py 检查是否有运行中的 DataService
3. 如果没有，fork 子进程启动 DataService
4. TUI/GUI 作为客户端通过 stdio JSON 与 DataService 通信

### 3.3 通信协议

**请求格式（客户端 → DataService）：**
```json
{"action": "get_markets"}
{"action": "refresh_data"}
{"action": "analyze", "code": "600519"}
{"action": "get_config"}
{"action": "update_config", "data": {...}}
```

**响应格式（DataService → 客户端）：**
```json
{"status": "ok", "data": {...}}
{"status": "error", "message": "..."}
{"type": "push", "data": {"markets": [...], "timestamp": "..."}}
```

---

## 四、数据流向

### 4.1 客户端启动
```
TUI/GUI 启动
    ↓
连接 DataService (stdio)
    ↓
发送 init 请求
    ↓
DataService 返回当前数据（缓存 or 空）
    ↓
客户端展示界面
```

### 4.2 定时刷新
```
DataService 定时器 (30s)
    ↓
拉取 AkShare/YFinance 数据
    ↓
更新 SQLite 缓存
    ↓
主动推送数据到客户端
    ↓
客户端更新界面显示
```

### 4.3 手动刷新
```
用户按 r (TUI) 或点击刷新 (GUI)
    ↓
客户端发送 refresh_data 请求
    ↓
DataService 立即拉取数据
    ↓
推送新数据到客户端
```

### 4.4 AI 分析
```
用户输入股票代码
    ↓
客户端发送 analyze 请求
    ↓
DataService 执行分析 Pipeline
    ↓
发送分析结果 + 推送通知
    ↓
客户端展示结果
```

---

## 五、模块设计

### 5.1 main.py（唯一入口）

```
职责：
- 检测并 fork DataService 进程
- 根据参数选择 TUI 或 GUI 模式
- 管理子进程生命周期
```

### 5.2 DataService（后端守护进程）

```
职责：
- 数据拉取（AkShare/YFinance）
- SQLite 缓存管理
- 定时推送数据
- AI 分析执行
- 配置管理

接口：
- stdio JSON 通信
- 监听 stdin，输出到 stdout
```

### 5.3 TUI / GUI（客户端界面）

```
职责：
- 用户交互
- 数据显示
- 请求发送

通信：
- 通过 stdin/stdout 发送 JSON 请求到 DataService
- 接收 DataService 的响应和推送数据
```

---

## 六、配置文件

### 6.1 配置文件位置

`~/.open-daily-stock/config.json` 或 `config.json`（工作目录）

### 6.2 配置结构

```json
{
  "stocks": ["600519", "000001"],
  "apis": {
    "gemini_key": "xxx",
    "deepseek_key": "xxx"
  },
  "notifications": {
    "wecom_webhook": "xxx",
    "feishu_webhook": "xxx",
    "telegram_bot_token": "xxx",
    "smtp_email": "xxx"
  },
  "refresh_interval": 30,
  "ui_mode": "gui"
}
```

### 6.3 首次启动引导

首次运行检测到无配置文件 → 启动引导流程：
1. 提示用户输入 API keys
2. 提示用户输入自选股列表
3. 保存配置到 config.json
4. 启动主界面

---

## 七、设计思想

### 7.1 单一入口

`main.py` 是唯一入口，根据参数或自动检测选择 TUI/GUI 模式。DataService 作为子进程运行，客户端不感知进程管理细节。

### 7.2 界面与后端分离

TUI 和 GUI 共享同一个 DataService 后端，数据完全一致。界面层只负责交互，不处理业务逻辑。

### 7.3 缓存优先

DataService 维护本地 SQLite 缓存，即使数据源不可用也能展示历史数据。

### 7.4 主动推送

DataService 定时拉取数据并主动推送到客户端，客户端无需频繁轮询。

---

## 八、实现细节

### 8.1 DataService 启动

```python
# main.py
import subprocess
import sys

def start_data_service():
    proc = subprocess.Popen(
        [sys.executable, '-m', 'src.data_service'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return proc
```

### 8.2 JSON 通信

```python
# 发送请求
proc.stdin.write(json.dumps({"action": "get_markets"}).encode())
proc.stdin.flush()

# 接收响应
data = json.loads(proc.stdout.readline())
```

### 8.3 定时推送

```python
# DataService
class DataService:
    def __init__(self):
        self._timer = threading.Timer(30, self._push_markets)
        self._timer.start()

    def _push_markets(self):
        data = self._fetch_markets()
        self._push({"type": "push", "data": data})
```

---

## 九、非目标（Out of Scope）

- 不支持 Web UI
- 不支持远程服务器管理
- 不实现 K 线图等复杂图表（仅数值展示）
- 不支持回测功能
- 不需要 Docker 部署