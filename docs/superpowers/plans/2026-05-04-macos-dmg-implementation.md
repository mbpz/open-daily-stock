# macOS DMG 打包实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GUI 版本打包成 macOS `.app` bundle 和 DMG 安装包

**Architecture:** 使用 PyInstaller 打包可执行文件，手动创建 .app Bundle 结构，然后用 create-dmg 生成 DMG 镜像

**Tech Stack:** PyInstaller, create-dmg, bash script, GitHub Actions

---

## 文件结构

```
scripts/
└── package-macos-app.sh    # 打包脚本（新建）

.github/workflows/
└── release-dmg.yml         # DMG CI 流程（新建）
```

---

## Task 1: 创建打包脚本

**文件:**
- 创建: `scripts/package-macos-app.sh`

- [ ] **Step 1: 创建 scripts 目录**

```bash
mkdir -p scripts
```

- [ ] **Step 2: 创建打包脚本**

```bash
#!/bin/bash
set -e

# 默认版本从 git tag 获取
VERSION=${1:-$(git describe --tags 2>/dev/null | sed 's/^v//')}
if [ -z "$VERSION" ]; then
    VERSION="0.0.0"
fi

echo "Packaging open-daily-stock GUI v$VERSION for macOS"

# 清理旧的 dist
rm -rf dist

# 1. PyInstaller 打包 (在 gui 目录下)
cd gui
pyinstaller open-daily-stock.spec --distpath ../dist
cd ..

# 2. 创建 .app Bundle 结构
APPNAME="open-daily-stock-gui.app"
BUNDLE_PATH="dist/$APPNAME"
CONTENTS="$BUNDLE_PATH/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

mkdir -p "$MACOS"
mkdir -p "$RESOURCES"

# 复制可执行文件
cp "dist/open-daily-stock-gui" "$MACOS/"

# 创建 Info.plist
cat > "$CONTENTS/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>open-daily-stock-gui</string>
    <key>CFBundleDisplayName</key>
    <string>Open Daily Stock</string>
    <key>CFBundleIdentifier</key>
    <string>com.opendailystock.gui</string>
    <key>CFBundleVersion</key>
    <string>__VERSION__</string>
    <key>CFBundleShortVersionString</key>
    <string>__VERSION__</string>
    <key>CFBundleExecutable</key>
    <string>open-daily-stock-gui</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF

# 替换版本号
sed -i '' "s/__VERSION__/$VERSION/g" "$CONTENTS/Info.plist"

# 3. 创建 DMG
DMG_NAME="dist/open-daily-stock-gui-$VERSION-macos.dmg"

if ! command -v create-dmg &> /dev/null; then
    echo "create-dmg not found, installing via brew..."
    brew install create-dmg
fi

create-dmg \
    --volname "Open Daily Stock" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "$BUNDLE_PATH" 200 150 \
    --hide-extension "$APPNAME" \
    --app-drop-link 400 150 \
    "$DMG_NAME" \
    "$BUNDLE_PATH"

echo "Done! DMG created: $DMG_NAME"
```

- [ ] **Step 3: 添加执行权限并提交**

```bash
chmod +x scripts/package-macos-app.sh
git add scripts/package-macos-app.sh
git commit -m "feat: add macOS DMG packaging script"
```

---

## Task 2: 创建 CI 流程

**文件:**
- 创建: `.github/workflows/release-dmg.yml`

- [ ] **Step 1: 创建 CI workflow 文件**

```yaml
name: Release DMG

on:
  push:
    tags:
      - 'v*'

jobs:
  build-dmg:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller textual flet>=0.25.0

      - name: Install create-dmg
        run: brew install create-dmg

      - name: Run packaging script
        env:
          GITHUB_REF_NAME: ${{ github.ref_name }}
        run: |
          TAG_VERSION=$(echo "$GITHUB_REF_NAME" | sed 's/^v//')
          ./scripts/package-macos-app.sh "$TAG_VERSION"

      - name: Upload DMG
        uses: actions/upload-artifact@v4
        with:
          name: open-daily-stock-gui-dmg
          path: dist/open-daily-stock-gui-*.dmg
          retention-days: 30

      - name: Upload App Bundle
        uses: actions/upload-artifact@v4
        with:
          name: open-daily-stock-gui-app
          path: dist/open-daily-stock-gui.app
          retention-days: 30
```

- [ ] **Step 2: 提交 CI 文件**

```bash
git add .github/workflows/release-dmg.yml
git commit -m "ci: add DMG release workflow"
```

---

## Task 3: 本地测试打包

- [ ] **Step 1: 检查 create-dmg 安装**

```bash
brew install create-dmg
```

- [ ] **Step 2: 运行打包脚本**

```bash
./scripts/package-macos-app.sh 0.3.6
```

- [ ] **Step 3: 验证产出物**

```bash
ls -la dist/
# 应该看到:
# open-daily-stock-gui (可执行文件)
# open-daily-stock-gui.app (bundle)
# open-daily-stock-gui-0.3.6-macos.dmg (DMG)
```

- [ ] **Step 4: 测试 .app 是否可以启动（可选）**

```bash
open dist/open-daily-stock-gui.app
```

---

## Task 4: 触发 CI 验证

- [ ] **Step 1: 创建测试 tag 并推送**

```bash
git tag v0.3.6-test && git push origin v0.3.6-test
```

- [ ] **Step 2: 等待 CI 完成并检查结果**

```bash
gh run list --workflow release-dmg.yml --limit 1
gh api repos/mbpz/open-daily-stock/actions/runs/$(gh run list --workflow release-dmg.yml --limit 1 --json id --jq '.[0].id')/jobs
```

- [ ] **Step 3: 清理测试 tag**

```bash
git tag -d v0.3.6-test
git push origin --delete v0.3.6-test
```

---

## 验证清单

- [ ] `scripts/package-macos-app.sh` 可执行且生成正确产出物
- [ ] `dist/open-daily-stock-gui` 可执行文件存在
- [ ] `dist/open-daily-stock-gui.app` 是有效的 .app bundle
- [ ] `dist/open-daily-stock-gui-*.dmg` DMG 文件存在
- [ ] CI `release-dmg.yml` 在 tag push 时触发
- [ ] CI 产出的 DMG 可下载

---

## 已知限制

- macOS 10.15+ 支持
- Apple Silicon 和 Intel 均支持
- 用户需在系统偏好设置中允许"任何来源"运行（首次运行）
