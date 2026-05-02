# Flet 桌面客户端设计方案

**项目定位：** 真正的桌面窗口应用，替代现有 TUI，面向不熟悉命令行的用户

## 架构

```
open-daily-stock/
├── main.py              # 入口：根据 --gui 参数选择启动
├── gui/                 # Flet 桌面客户端（新增）
│   ├── main.py          # gui 入口
│   ├── app.py          # Flet App 主类
│   ├── pages/          # 页面
│   │   ├── markets.py  # 行情页
│   │   ├── analyze.py  # 分析页
│   │   ├── tasks.py    # 任务页
│   │   ├── config.py   # 配置页
│   │   └── logs.py     # 日志页
│   ├── components/     # 通用组件
│   └── theme.py        # 主题/样式
├── tui/                 # 现有 TUI（保留）
│   └── ...
└── src/                 # 核心业务（共享）
    ├── config.py
    ├── analyzer.py
    └── ...
```

## 布局

- **左侧导航栏**（宽度 60px）：图标 + 文字，点击切换页面
- **右侧内容区**：显示当前页面内容
- **顶部状态栏**：显示最后更新时间、连接状态

## 页面功能

| 页面 | 功能 |
|------|------|
| 行情 | 自选股列表，点击行可看详情，30s 自动刷新 |
| 分析 | 输入股票代码，触发分析，显示结果 |
| 任务 | 历史分析任务列表 |
| 配置 | API Key、数据源、通知设置（首次向导也走这） |
| 日志 | 运行日志查看 |

## 技术栈

| 组件 | 技术 |
|------|------|
| UI 框架 | Flet |
| 核心业务 | 复用 src/ |
| 数据获取 | 复用 data_provider/ |
| 打包 | PyInstaller |

## 入口参数

| 参数 | 行为 |
|------|------|
| `python main.py` | 启动 WebUI（现有行为） |
| `python main.py --gui` | 启动 Flet 桌面客户端 |
| `python main.py --tui` | 启动 Textual TUI（保留） |

## 依赖

```txt
# 新增依赖
flet>=0.25.0
```

## 打包

```bash
# Windows
pyinstaller --onefile --console gui/main.py

# macOS
pyinstaller --onefile --console gui/main.py
```

## 待设计细节

- [ ] 首次启动向导（与 TUI Wizard 类似）
- [ ] 行情页面具体布局（表格/卡片）
- [ ] 分析结果展示格式
- [ ] 任务状态显示方式
