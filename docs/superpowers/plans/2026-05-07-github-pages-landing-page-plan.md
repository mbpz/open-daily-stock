# GitHub Pages Landing Page 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 GitHub Pages Landing Page，通过 MkDocs 自动构建并发布

**Architecture:** 使用 MkDocs Material 生成静态站点，GitHub Actions 自动部署到 GitHub Pages

**Tech Stack:** MkDocs, MkDocs Material, GitHub Actions, GitHub Pages

---

## 文件结构

```
mkdocs.yml                    # MkDocs 站点配置
docs/
├── index.md                 # Landing page 首页
└── screenshots/            # 截图目录（用户需手动添加）
.github/workflows/
└── pages.yml               # GitHub Pages 发布流程
```

---

## Task 1: 创建 MkDocs 配置文件

**文件:**
- 创建: `mkdocs.yml`

- [ ] **Step 1: 创建 mkdocs.yml**

```yaml
site_name: Open Daily Stock
site_description: A股/港股/美股自选股智能分析系统
site_url: https://mbpz.github.io/open-daily-stock/
site_author: mbpz

repo_name: mbpz/open-daily-stock
repo_url: https://github.com/mbpz/open-daily-stock

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.sections
    - navigation.expand
    - toc.integrate
    - search.suggest
    - search.highlight

nav:
  - Home: index.md

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/mbpz/open-daily-stock
```

- [ ] **Step 2: 提交文件**

```bash
git add mkdocs.yml
git commit -m "feat: add mkdocs configuration for GitHub Pages"
```

---

## Task 2: 创建 Landing Page 首页

**文件:**
- 创建: `docs/index.md`

- [ ] **Step 1: 创建 docs 目录和 index.md**

```markdown
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
```

- [ ] **Step 2: 创建截图目录占位**

```bash
mkdir -p docs/screenshots
# 添加占位文件说明需要添加截图
echo "请将 tui.png 和 gui.png 截图添加到本目录" > docs/screenshots/README.md
```

- [ ] **Step 3: 提交文件**

```bash
git add docs/index.md docs/screenshots/
git commit -m "feat: add landing page content"
```

---

## Task 3: 创建 GitHub Actions CI

**文件:**
- 创建: `.github/workflows/pages.yml`

- [ ] **Step 1: 创建 CI workflow**

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
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install mkdocs-material

      - name: Build site
        run: mkdocs gh-deploy --force --verbose

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: 提交文件**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: add GitHub Pages deployment workflow"
```

---

## Task 4: 本地测试构建

- [ ] **Step 1: 安装 MkDocs**

```bash
pip install mkdocs-material
```

- [ ] **Step 2: 本地构建预览**

```bash
mkdocs serve
# 访问 http://localhost:8000 查看
```

- [ ] **Step 3: 验证构建（无截图情况）**

```bash
mkdocs build
# 检查 site/ 目录是否生成
ls -la site/
```

---

## Task 5: GitHub Pages 启用配置

此任务需要用户在 GitHub 网页上手动操作：

- [ ] **Step 1: 访问 GitHub Settings**

打开 https://github.com/mbpz/open-daily-stock/settings/pages

- [ ] **Step 2: 配置 Source**

- Source: GitHub Actions
- Branch: main (不需要选择，具体由 workflow 控制)

- [ ] **Step 3: 触发首次部署**

```bash
git push origin main
# 或手动触发 workflow
```

---

## 验证清单

- [ ] `mkdocs.yml` 配置文件存在且有效
- [ ] `docs/index.md` Landing page 内容完整
- [ ] `.github/workflows/pages.yml` CI 文件存在
- [ ] 本地 `mkdocs build` 成功生成 site/ 目录
- [ ] GitHub Pages 在 Settings 中启用并选择 GitHub Actions 作为来源
- [ ] push 到 main 后 CI 自动触发并成功
- [ ] GitHub Pages URL 可访问

---

## 已知限制

- 截图需要用户手动添加（docs/screenshots/tui.png 和 docs/screenshots/gui.png）
- GitHub Pages 首次启用需要手动在 Settings 中配置
- 站点 URL 将是: https://mbpz.github.io/open-daily-stock/
