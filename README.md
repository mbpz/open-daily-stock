# 📈 open-daily-stock

A 股/港股/美股自选股智能分析系统，纯本地 PC 端 TUI 应用。

## 功能特性

- **TUI 界面** — 终端交互，行情 30s 自动轮询
- **多数据源** — AkShare（免费 A 股）、YFinance（港美股）
- **AI 分析** — Google Gemini / OpenAI 兼容 API
- **多渠道推送** — 企业微信、飞书、Telegram、邮件
- **一键安装** — PyInstaller 打包，用户下载即用

## 快速开始

### 启动 TUI

```bash
python main.py --tui
```

**快捷键**

| 快捷键 | 功能 |
|--------|------|
| `1-5` / `Tab` | 切换模块 |
| `r` | 手动刷新行情 |
| `q` | 退出 |

**五个模块**

| 快捷键 | 模块 | 说明 |
|--------|------|------|
| `1` | Markets | 自选股实时行情 |
| `2` | Tasks | 分析任务历史 |
| `3` | Analyze | 手动触发分析 |
| `4` | Config | 配置管理 |
| `5` | Logs | 日志查看 |

### 命令行模式

```bash
python main.py                    # 完整分析 + 推送
python main.py --dry-run          # 仅获取数据
```

## 下载可执行文件

每次打 tag 自动构建三个平台 Release：

- **Linux**: `open-daily-stock`
- **macOS**: `open-daily-stock-macos`
- **Windows**: `open-daily-stock.exe`

下载地址：https://github.com/mbpz/open-daily-stock/releases

## 项目结构

```
open-daily-stock/
├── main.py              # 主入口
├── tui/                 # TUI 界面
│   ├── app.py          # Textual App
│   └── widgets/        # 各模块视图
├── src/                 # 核心业务
│   ├── analyzer.py     # AI 分析器
│   ├── config.py       # 配置管理
│   └── notification.py # 通知推送
├── data_provider/       # 数据源适配器
└── .github/workflows/  # 构建流程
```

## 文档

- [ROADMAP.md](ROADMAP.md) — 功能规划
- [DESIGN.md](DESIGN.md) — 架构设计

## License

MIT
