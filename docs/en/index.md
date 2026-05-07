# Open Daily Stock

A-share / HK-stock / US-stock intelligent analysis system

## Features

- **Multi-Market Coverage** — A-shares (AkShare), HK stocks, US stocks (YFinance)
- **AI-Powered Analysis** — Gemini / DeepSeek / Tongyi and other LLMs for deep stock analysis
- **Dual Interface Mode** — TUI terminal / GUI desktop, switch as needed
- **Multi-Channel Notifications** — WeCom, Feishu, Telegram, Email alerts
- **Cross-Platform** — macOS, Linux, Windows support
- **Open Source & Free** — MIT License, fully open source

## Interface Preview

### TUI Terminal Interface

```
┌─────────────────────────────────────────────────────────────┐
│  [1] Markets    [2] Tasks    [3] Analyze    [4] Config    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   📈 Watchlist                      Updated: 2024-01-15   │
│   ────────────────────────────────────────────────────────  │
│   Symbol     Name           Price     Change    Amount     │
│   ────────────────────────────────────────────────────────  │
│   600519    Kweichow Moutai  1850.00  +2.35%   +42.50   │
│   000001    Ping An Bank       12.85  -0.85%   -0.11    │
│   00700     Tencent           385.20  +1.25%   +4.76    │
│   AAPL      Apple Inc         185.50  +0.52%   +0.96    │
│                                                             │
│   [R] Refresh    [Q] Quit                                   │
└─────────────────────────────────────────────────────────────┘
```

### GUI Desktop Interface

```
┌─────────────────────────────────────────────────────────────┐
│  Open Daily Stock                              v0.3.7  ⟳  │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  📊 Market│   Symbol     Name           Price     Change  │
│  📉 Chart │   ────────────────────────────────────────────  │
│  🔍 Analyze│   600519    Kweichow Moutai  1850.00  +2.35% │
│  📋 Tasks │   000001    Ping An Bank       12.85  -0.85%  │
│  ⚙️ Config│   00700     Tencent           385.20  +1.25%  │
│  📜 Logs │   AAPL      Apple Inc         185.50  +0.52%  │
│          │                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

## Installation

### macOS

1. Download `open-daily-stock-gui-x.x.x-macos.dmg`
2. Double-click to mount, drag **Open Daily Stock.app** to Applications
3. Launch from Applications folder

### Linux

```bash
# Download and extract
wget https://github.com/mbpz/open-daily-stock/releases/latest/download/open-daily-stock-linux.tar.gz
tar -xzf open-daily-stock-linux.tar.gz
chmod +x open-daily-stock
./open-daily-stock
```

### Windows

Download `open-daily-stock.exe`, double-click to run.

## Download

**[GitHub Releases](https://github.com/mbpz/open-daily-stock/releases/latest)** — Download latest version

## Project Structure

```
open-daily-stock/
├── main.py              # Main entry (auto-selects TUI/GUI)
├── src/                 # Core modules
│   ├── data_service.py  # Backend daemon
│   ├── analyzer.py      # AI analyzer
│   ├── config.py        # Configuration
│   └── notification.py  # Notifications
├── tui/                 # TUI interface (Textual)
└── gui/                 # GUI interface (Flet)
```

## License

MIT License - See [GitHub](https://github.com/mbpz/open-daily-stock/blob/main/LICENSE)
