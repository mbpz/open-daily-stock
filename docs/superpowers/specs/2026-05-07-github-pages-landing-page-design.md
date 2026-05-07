# GitHub Pages Landing Page 设计

**日期**: 2026-05-07
**状态**: 已批准

## 目标

为 open-daily-stock 项目创建一个产品展示型 Landing Page，通过 GitHub Pages 自动发布，帮助用户快速了解项目并下载使用。

## 设计风格

**产品展示风格** — 清晰实用，以内容为主：
- 项目截图展示
- 功能特性列表
- 安装使用步骤
- 下载链接

## 页面结构

```
┌─────────────────────────────────────────────┐
│  Header: Logo + 项目名称 + GitHub 链接       │
├─────────────────────────────────────────────┤
│  Hero Section:                              │
│    - 一句话介绍项目                          │
│    - 核心功能亮点（3-4 条）                  │
│    - 下载按钮（TUI / GUI）                   │
├─────────────────────────────────────────────┤
│  Screenshots Section:                       │
│    - TUI 界面截图                           │
│    - GUI 界面截图                           │
├─────────────────────────────────────────────┤
│  Features Section:                          │
│    - 多数据源（A股/港股/美股）               │
│    - AI 智能分析                            │
│    - 多渠道推送                            │
│    - 跨平台支持                            │
├─────────────────────────────────────────────┤
│  Installation Section:                      │
│    - macOS 安装步骤                         │
│    - Linux 安装步骤                         │
│    - Windows 安装步骤                       │
├─────────────────────────────────────────────┤
│  Footer:                                    │
│    - License + GitHub 链接                  │
└─────────────────────────────────────────────┘
```

## 技术方案

### 静态站点生成

使用 **MkDocs Material** 生成静态站点：
- 配置简单，专注内容
- Material Design 主题美观
- 自动生成导航、搜索、代码高亮
- 支持 Markdown 编写

### 目录结构

```
docs/
└── site/              # 生成的静态站点（CI 自动构建）
mkdocs.yml             # MkDocs 配置
docs/
└── index.md          # 首页内容
```

### GitHub Pages CI

**触发条件**: push 到 main 分支时自动构建并发布

**工作流程**:
1. Checkout 代码
2. 安装 MkDocs 和 Material 主题
3. 执行 `mkdocs gh-deploy` 自动发布到 GitHub Pages

## 新增文件

| 文件 | 说明 |
|------|------|
| `mkdocs.yml` | MkDocs 站点配置 |
| `docs/index.md` | Landing page 首页内容 |
| `.github/workflows/pages.yml` | GitHub Pages 发布流程 |

## CI 设计

```yaml
name: Deploy GitHub Pages
on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install MkDocs
        run: pip install mkdocs-material

      - name: Build site
        run: mkdocs gh-deploy --force

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy-pages:
    needs: deploy
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

## 页面内容 (docs/index.md)

```markdown
# Open Daily Stock

A 股 / 港股 / 美股自选股智能分析系统

## 核心特性

- **多市场覆盖** — A 股（AkShare）、港股、美股（YFinance）
- **AI 智能分析** — Gemini / DeepSeek / 通义等大模型
- **双模式界面** — TUI 终端 / GUI 图形，按需切换
- **多渠道推送** — 企业微信、飞书、Telegram、邮件
- **跨平台支持** — macOS、Linux、Windows

## 界面预览

![TUI](screenshots/tui.png)
![GUI](screenshots/gui.png)

## 安装使用

### macOS

1. 下载 DMG 安装包
2. 挂载后将应用拖入 Applications
3. 双击启动

### Linux

```bash
wget https://github.com/mbpz/open-daily-stock/releases/latest/download/open-daily-stock
chmod +x open-daily-stock
./open-daily-stock
```

### Windows

下载 exe 文件，双击运行。

## 下载地址

- [GitHub Releases](https://github.com/mbpz/open-daily-stock/releases)

## License

MIT
```

## 截图方案

由于 CI 自动构建，截图需要用户提供：
- `docs/screenshots/tui.png` — TUI 界面截图
- `docs/screenshots/gui.png` — GUI 界面截图

## 已知限制

- 首次需要启用 GitHub Pages 和选择 "GitHub Actions" 作为来源
- 截图需要手动准备并添加到仓库

## TODO

- [ ] 创建 `mkdocs.yml` 配置文件
- [ ] 创建 `docs/index.md` 首页内容
- [ ] 创建 `.github/workflows/pages.yml` CI 流程
- [ ] 在 GitHub Settings 启用 GitHub Pages
- [ ] 添加截图到 `docs/screenshots/` 目录
