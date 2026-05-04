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

## 三、PC Client 新架构（开发中）

### 3.1 DataService 后端

| 功能 | 状态 |
|------|------|
| 后端守护进程 fork 管理 | ✅ |
| stdio JSON 通信协议 | ✅ |
| SQLite 数据持久化 | ✅ |
| 定时拉取 + 主动推送 | ✅ |
| 进程崩溃恢复 | ✅ |

### 3.2 双模式功能对等

| 功能 | TUI | GUI |
|------|-----|-----|
| 行情展示 | ✅ | ✅ |
| AI 分析触发 | ✅ | ✅ |
| 配置管理 | ✅ | ✅ |
| 首次启动引导 | ✅ | ✅ |
| 任务历史 | ✅ | ✅ |
| 日志查看 | ✅ | ✅ |

---

## 四、待完成功能

### 高优先级

- [x] DataService 后端实现（stdio 通信）✅
- [x] TUI/GUI 双模式功能对等 ✅
- [x] 首次启动引导（API Key 配置）✅
- [x] 自动更新完善（GUI 状态栏更新按钮）✅

### 中优先级

- [x] 行情异动提醒（涨跌超 5% 弹窗/通知）✅
- [x] 分析进度显示 ✅
- [x] 日志搜索/过滤 ✅
- [x] 快捷键帮助面板（`?` 键 TUI）✅

### 低优先级

- [x] 历史分析回放 ✅
- [x] K 线图表展示 ✅
- [x] 多语言支持 ✅

---

## 五、技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| GUI 框架 | Flet >= 0.25 |
| 数据获取 | AkShare、YFinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API |
| 数据库 | SQLite |
| 进程通信 | stdio JSON |
| 打包 | PyInstaller |
| 构建 | GitHub Actions |

---

## 六、项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口
├── src/
│   ├── data_service.py  # 后端守护进程
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   ├── pipeline.py      # 分析管线
│   ├── notification.py  # 通知推送
│   ├── update_service.py # 自动更新
│   └── refresh_service.py # 数据刷新
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