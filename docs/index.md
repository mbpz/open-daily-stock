# Open Daily Stock

A 股 / 港股 / 美股自选股智能分析系统

## 核心特性

<div class="grid cards" markdown>

- **多市场覆盖**
  A 股（AkShare）、港股、美股（YFinance）一网打尽

- **AI 智能分析**
  Gemini / DeepSeek / 通义等大模型，深度解读股票走势

- **双模式界面**
  TUI 终端 / GUI 图形，按需切换

- **多渠道推送**
  企业微信、飞书、Telegram、邮件及时通知

- **跨平台支持**
  macOS、Linux、Windows 全平台覆盖

- **开源免费**
  MIT License，完全开源

</div>

## 界面预览

### TUI 终端界面

![TUI 界面](screenshots/tui.png)

### GUI 图形界面

![GUI 界面](screenshots/gui.png)

## 安装使用

### macOS

1. 下载 `open-daily-stock-gui-x.x.x-macos.dmg`
2. 双击挂载后将 **Open Daily Stock.app** 拖入 Applications
3. 从 Applications 文件夹启动

### Linux

```bash
# 下载解压
wget https://github.com/mbpz/open-daily-stock/releases/latest/download/open-daily-stock-linux.tar.gz
tar -xzf open-daily-stock-linux.tar.gz
chmod +x open-daily-stock
./open-daily-stock
```

### Windows

下载 `open-daily-stock.exe`，双击运行。

## 下载地址

[:material-github: GitHub Releases](https://github.com/mbpz/open-daily-stock/releases/latest){ .md-button .md-button--primary }

## 项目结构

```
open-daily-stock/
├── main.py              # 唯一主入口（TUI/GUI 自动选择）
├── src/                 # 核心模块
│   ├── data_service.py  # 后端守护进程
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   └── notification.py  # 通知推送
├── tui/                 # TUI 界面（Textual）
└── gui/                 # GUI 界面（Flet）
```

## License

MIT License - 详见 [GitHub](https://github.com/mbpz/open-daily-stock/blob/main/LICENSE)