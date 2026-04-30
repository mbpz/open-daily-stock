# open-daily-stock 设计文档

---

## 一、项目定位

**纯本地 PC 端 TUI 应用**。用户下载打包好的可执行文件，双击运行即可使用所有功能，无需安装 Python、无需配置服务端、无需 Docker。

**核心场景：** 用户在本地终端查看自选股行情、手动触发股票分析、配置通知渠道。

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

### 2.3 零配置启动
- 用户安装即用
- 配置项通过 TUI Config 模块在线修改
- 不需要手动编辑配置文件

### 2.4 单一职责
- TUI 只负责交互（展示、输入、导航）
- 业务逻辑在 src/（可被 main.py CLI 复用）
- 数据获取在 data_provider/（可被 TUI 和 CLI 共用）

---

## 三、架构设计

### 3.1 分层结构

```
┌─────────────────────────────────────┐
│           TUI 层（交互）             │
│  Textual App · 5 个模块视图         │
└──────────────┬────────────────────┘
               │
┌──────────────┴────────────────────┐
│         核心业务层                   │
│  src/analyzer · config · storage    │
│  src/notification · search_service │
└──────────────┬────────────────────┘
               │
┌──────────────┴────────────────────┐
│         数据层                     │
│  data_provider/ · SQLite          │
│  (AkShare · YFinance)             │
└───────────────────────────────────┘
```

### 3.2 数据流向

```
用户操作（TUI）
    ↓
TUIApp（路由 + 状态管理）
    ↓
DataProviderWrapper（获取行情）
    ↓
AkShare / YFinance（免费数据源）
    ↓
MarketsView（展示）
    ↓
状态栏更新（Footer.set_last_update）
```

### 3.3 各模块数据流

| 模块 | 数据来源 | 持久化 |
|------|----------|--------|
| Markets | DataProviderWrapper → AkShare/YFinance | 否（内存） |
| Tasks | TaskStore（内存） | 否 |
| Analyze | 调用 src/core/pipeline.py | 否 |
| Config | src/config.py → .env | 是（写入 .env） |
| Logs | logs/ 目录下的日志文件 | 是（日志文件） |

---

## 四、用户交互流程

### 4.1 首次使用

```
启动 TUI
    ↓
Markets 模块默认显示（无数据）
    ↓
用户按 r 手动刷新
    ↓
获取自选股行情并展示
    ↓
30s 自动轮询刷新
```

### 4.2 手动分析流程

```
用户切换到 Analyze 模块（按 2）
    ↓
输入股票代码（如 600519）
    ↓
按 Enter 或点击"开始分析"
    ↓
TaskStore 添加任务（状态：pending）
    ↓
Pipeline 运行分析
    ↓
任务状态更新（pending → running → done/failed）
    ↓
结果推送到通知渠道
    ↓
TUI 内显示分析结果
```

### 4.3 配置修改流程

```
用户切换到 Config 模块（按 4）
    ↓
编辑自选股列表输入框
    ↓
按 Enter 保存
    ↓
src.config.stock_list 更新
    ↓
.env 文件同步写入
    ↓
Markets 模块自动使用新列表
```

---

## 五、模块设计

### 5.1 TUIApp（路由中心）

```
职责：
- 管理全局状态（_current, _dp, _task_store）
- 协调 5 个模块的显示/隐藏
- 处理全局快捷键（1-5/Tab/r/q）
- 维护自动轮询定时器
```

### 5.2 各模块职责

| 模块 | 职责边界 |
|------|----------|
| MarketsView | 只负责行情展示，不处理数据获取 |
| TasksView | 只负责任务列表展示，不处理任务执行 |
| AnalyzeView | 只负责输入收集，调用回调函数 |
| ConfigView | 只负责配置展示和编辑，调用 src.config |
| LogsView | 只负责日志读取和展示，不处理日志写入 |

### 5.3 状态传递

```
TUIApp.__init__
    ├── self._dp = DataProviderWrapper  (共享)
    ├── self._task_store = TaskStore    (共享)
    └── self._on_analyze_callback = ...  (回调)

compose()
    ├── MarketsView(self._dp)
    ├── TasksView(self._task_store)
    ├── AnalyzeView(self._on_analyze_callback)
    ├── ConfigView()
    └── LogsView()
```

---

## 六、实现细节

### 6.1 Textual 布局

```
Screen
├── Header (固定高度 1)
├── Nav (固定高度 1)
├── Content Area (动态高度)
│   ├── MarketsView (display=当前模块)
│   ├── TasksView (display=非当前模块)
│   ├── AnalyzeView
│   ├── ConfigView
│   └── LogsView
└── Footer (固定高度 1)
```

切换模块：通过 `action_switch(idx)` 设置 `display=True/False`

### 6.2 行情轮询

```python
# TUIApp._start_polling
self._poll_timer = self.set_interval(self._dp.poll_interval, poll)

# poll() 是 async 函数
async def poll():
    await self._dp.fetch_all()      # 获取数据
    markets.refresh()               # 刷新 MarketsView
    footer.set_last_update(...)    # 更新 Footer 时间戳
```

### 6.3 任务状态流转

```
用户触发分析
    ↓
TaskStore.add_task(code) → status=PENDING
    ↓
Pipeline.start → status=RUNNING
    ↓
Pipeline.done → status=DONE
    ↓
Pipeline.error → status=FAILED
```

### 6.4 配置持久化

```python
# ConfigView.on_input_submitted
self._config.stock_list = new_list  # 内存更新
# src.config 模块负责写入 .env
```

---

## 七、设计思想

### 7.1 TUI 是交互层，不是业务层

**错误做法：**
```python
class MarketsView:
    def on_button_pressed(self):
        # 在 View 里直接调用 API
        data = ak.stock_zh_a_spot_em()
```

**正确做法：**
```python
class MarketsView:
    def __init__(self, data_provider):
        self._dp = data_provider  # 注入依赖

    def render(self):
        data = self._dp.get_data()  # View 只展示数据
```

### 7.2 业务逻辑不依赖 TUI

src/ 下的模块可以被 main.py（CLI）直接调用，TUI 只是新增了一个交互入口。

### 7.3 数据获取与展示分离

```
DataProviderWrapper (数据层) ← 获取数据、缓存、自动轮询
MarketsView (展示层) ← 只调用 get_data() 获取数据进行渲染
```

### 7.4 配置集中管理

所有配置通过 `src.config.get_config()` 集中访问，不在各个模块里分散读取环境变量。

---

## 八、非目标（Out of Scope）

- 不支持 Web UI
- 不支持远程服务器管理
- 不实现 K 线图等复杂图表（仅数值展示）
- 不支持回测功能
- 不需要 Docker 部署
