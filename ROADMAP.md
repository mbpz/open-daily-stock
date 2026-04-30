# open-daily-stock Roadmap

**项目定位：** 纯本地 PC 端 TUI 应用，无需服务端，打包后用户安装即可使用所有功能。

---

## 一、TUI 界面（已完成）

### 1.1 五个模块

| 模块 | 功能 | 状态 |
|------|------|------|
| Markets | 自选股实时行情，30s 自动轮询 | ✅ |
| Tasks | 分析任务历史记录 | ✅ |
| Analyze | 手动输入股票代码触发分析 | ✅ |
| Config | 配置管理（自选股列表、数据源开关） | ✅ |
| Logs | 日志查看（从 logs/ 目录读取） | ✅ |

### 1.2 快捷键

| 快捷键 | 功能 |
|--------|------|
| `1-5` / `Tab` | 切换模块 |
| `r` | 手动刷新行情 |
| `q` | 退出 |

---

## 二、核心功能（进行中）

### 2.1 行情数据

| 功能 | 状态 |
|------|------|
| A 股实时行情（AkShare） | ✅ |
| 港股/美股行情（YFinance） | ✅ |
| 自选股列表管理 | ✅ |
| 手动刷新 | ✅ |
| 自动轮询（30s 可配置） | ✅ |
| 行情异动提醒（涨跌超 5% 状态栏提示） | 待实现 |

### 2.2 AI 分析

| 功能 | 状态 |
|------|------|
| Google Gemini API | ✅ |
| OpenAI 兼容 API（DeepSeek/通义等） | ✅ |
| 分析结果展示（决策仪表盘） | 待集成 |
| 分析进度显示 | 待实现 |

### 2.3 通知渠道

| 功能 | 状态 |
|------|------|
| 企业微信 Webhook | ✅ |
| 飞书 Webhook | ✅ |
| Telegram Bot | ✅ |
| 邮件通知（SMTP） | ✅ |
| 自定义 Webhook | ✅ |
| 推送状态反馈 | 待实现 |

### 2.4 数据存储

| 功能 | 状态 |
|------|------|
| SQLite 本地数据库 | ✅ |
| 分析历史记录 | 待完善 |
| 任务状态持久化 | 待实现 |

---

## 三、打包与发布（待完善）

| 功能 | 状态 |
|------|------|
| PyInstaller 打包 | ✅ |
| GitHub Actions 自动构建 | ✅ |
| 多平台 Release（Linux/macOS/Windows） | ✅ |
| 用户下载即用（不依赖 Python 环境） | 待验证 |

### 发布流程

```bash
# 打 tag 触发构建
git tag v0.2.0
git push origin v0.2.0
```

构建产物：https://github.com/mbpz/open-daily-stock/releases

---

## 四、待完成功能

### 高优先级

- [ ] AI 分析完整流程接入 TUI（Analyze 模块调用 Pipeline）
- [ ] 分析结果在 TUI 内展示
- [ ] 任务状态实时反馈（分析进度 %）
- [ ] 行情异动状态栏提醒

### 中优先级

- [ ] Config 模块完整配置项（数据源开关、通知渠道开关）
- [ ] 日志搜索/过滤功能
- [ ] 快捷键帮助面板（`?` 键）

### 低优先级

- [ ] 历史分析回放
- [ ] 图表展示（K 线等）
- [ ] 多语言支持

---

## 五、技术栈

| 组件 | 技术 |
|------|------|
| TUI 框架 | Textual |
| 数据获取 | AkShare、YFinance |
| AI 分析 | Google Gemini / OpenAI 兼容 API |
| 数据库 | SQLite |
| 打包 | PyInstaller |
| 构建 | GitHub Actions |

---

## 六、项目结构

```
open-daily-stock/
├── main.py              # 主入口
├── tui/                 # TUI 界面
│   ├── app.py          # Textual App
│   ├── widgets/        # 各模块视图
│   ├── data/          # DataProviderWrapper, TaskStore
│   └── styles/        # 主题颜色
├── src/                 # 核心业务
│   ├── analyzer.py     # AI 分析器
│   ├── config.py       # 配置管理
│   ├── notification.py # 通知推送
│   ├── storage.py      # 数据存储
│   └── core/          # 分析管线
├── data_provider/      # 数据源适配器
└── .github/
    └── workflows/     # 构建流程
```
