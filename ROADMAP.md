# open-daily-stock Roadmap

**项目定位：** 本地 PC 端 TUI + GUI 双模式应用，无需服务端，打包后用户安装即可使用所有功能。

---

## 一、TUI/GUI 双模式（核心架构）

| 模式 | 入口 | 说明 |
|------|------|------|
| GUI | `python main.py --gui` | Flet 图形界面，普通用户推荐 |
| TUI | `python main.py --tui` | Textual 终端界面，开发者/技术用户 |

**双模式架构：**

```
main.py (唯一入口)
    ↓
自动 fork DataService (后端守护进程)
    ↓ ↓
TUI 子进程    GUI 子进程
stdio JSON    stdio JSON
    ↓            ↓
←──── DataService (统一后端) ────→
```

---

## 二、已完成功能

### 2.1 行情数据

| 功能 | TUI | GUI |
|------|-----|-----|
| A 股实时行情（AkShare） | ✅ | ✅ |
| 港股/美股行情（YFinance） | ✅ | ✅ |
| 自选股列表管理 | ✅ | ✅ |
| 手动刷新 | ✅ | ✅ |
| 自动轮询（30s 可配置） | ✅ | ✅ |

### 2.2 AI 分析

| 功能 | TUI | GUI |
|------|-----|-----|
| Google Gemini API | ✅ | ✅ |
| OpenAI 兼容 API（DeepSeek/通义等） | ✅ | ✅ |
| 分析结果展示 | ✅ | ✅ |

### 2.3 通知渠道

| 功能 | TUI | GUI |
|------|-----|-----|
| 企业微信 Webhook | ✅ | ✅ |
| 飞书 Webhook | ✅ | ✅ |
| Telegram Bot | ✅ | ✅ |
| 邮件通知（SMTP） | ✅ | ✅ |
| 自定义 Webhook | ✅ | ✅ |

### 2.4 自动更新

| 功能 | 状态 |
|------|------|
| GitHub Releases 检查 | ✅ |
| GUI 状态栏更新按钮 | ✅ |
| CLI --check-update | ✅ |

---

## 三、重构任务（优化架构）

### 高优先级

- [ ] **P0-1: DataService Action 扩展**
  - 新增: `analyze` / `get_history` / `search_news` / `get_tasks` / `cancel_task`
  - 当前只有 4 个 action (hello/get_markets/refresh/quit)
  - 文件: `src/data_service.py`

- [ ] **P0-2: notification.py 模块化拆解**
  - 拆分为: `channels/` (wechat/feishu/telegram/email/discord) + `formatters.py` + `dispatcher.py`
  - 文件: `src/notification.py` (3112 行，需拆分)
  - 目标: 单文件 < 800 行

- [ ] **P0-3: search_service.py 模块化**
  - 拆分为: `search/bocha.py` + `tavily.py` + `serpapi.py` + `manager.py`
  - 文件: `src/search_service.py` (1079 行)

### 中优先级

- [ ] **P1-1: 数据层增强**
  - 添加 `schema_version` 字段支持数据库迁移
  - 行情历史表（用于 K 线回放）
  - 任务状态持久化

- [ ] **P1-2: TUI/GUI 代码复用**
  - 抽取公共组件到 `shared/` 目录
  - 减少重复开发

- [ ] **P1-3: 错误恢复增强**
  - DataService 崩溃后自动重启
  - 网络异常时本地缓存降级
  - AI API 429 限流自适应

### 低优先级

- [ ] **P2-1: 快捷键配置化**
  - 从硬编码改为 `config.json` 读取

- [ ] **P2-2: 主题切换**（深/浅色）

- [ ] **P2-3: 多语言扩展**（日语、韩语）

---

## 四、技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance、efinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API |
| 数据库 | SQLite |
| 进程通信 | stdio JSON |
| 打包 | PyInstaller |
| 构建 | GitHub Actions |

---

## 五、项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口
├── src/
│   ├── data_service.py  # 后端守护进程 [P0-1 重点]
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── notification.py  # 通知推送 [P0-2 拆分]
│   ├── search_service.py # 搜索服务 [P0-3 拆分]
│   ├── update_service.py # 自动更新
│   ├── refresh_service.py # 数据刷新
│   └── channels/       # [P0-2 拆分后] 通知渠道模块
│       ├── wechat.py
│       ├── feishu.py
│       ├── telegram.py
│       ├── email.py
│       └── discord.py
│   └── search/          # [P0-3 拆分后] 搜索模块
│       ├── bocha.py
│       ├── tavily.py
│       ├── serpapi.py
│       └── manager.py
├── tui/                 # TUI 界面
│   ├── app.py          # Textual App
│   └── widgets/        # 各模块视图
├── gui/                 # GUI 界面
│   ├── main.py         # Flet 入口
│   ├── app.py         # StockApp
│   └── pages/         # Markets/Analyze/Tasks/Config/Logs
├── data_provider/       # 数据源适配器
└── .github/
    ├── pyinstaller-hooks/
    └── workflows/       # 构建流程
```

---

## 六、重构优先级说明

### 为什么 P0-1 (DataService) 最优先？
- 当前 DataService 仅支持 4 个 action，但 TUI/GUI 客户端需要更多功能
- 瓶颈不突破，其他功能无法通过 stdio 调用

### 为什么 P0-2 (notification.py) 其次？
- 3112 行单文件，接近维护上限
- 新增通知渠道需要修改多处，耦合严重
- 拆分后可独立测试和复用

### 为什么 P0-3 (search_service.py) 第三？
- 1079 行，逻辑相对独立
- 拆分后可被 DataService 直接调用
- 支持多 Key 负载均衡

---

*最后更新: 2026-05-09*