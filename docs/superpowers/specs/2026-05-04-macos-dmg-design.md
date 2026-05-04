# macOS DMG 安装包设计

**日期**: 2026-05-04
**状态**: 已批准

## 目标

将 open-daily-stock GUI 版本打包成 macOS `.app` bundle，并生成 DMG 安装包，用户双击后拖拽到 Applications 即可使用。

## 方案概述

使用 PyInstaller 打包 + `.app` Bundle 结构 + DMG 镜像。

## 打包流程

```
源码 → PyInstaller 打包 → .app bundle 结构 → DMG 镜像
```

## 详细设计

### 1. PyInstaller 打包

**输入**: `gui/main.py`
**输出**: `dist/open-daily-stock-gui` (可执行文件)

**关键依赖**:
- `--onefile`: 单文件打包
- `--console`: GUI 应用无控制台窗口
- `--name`: open-daily-stock-gui
- `--additional-hooks-dir`: 包含 flet 依赖收集

**现有配置**:
```yaml
# gui/open-daily-stock.spec 已存在
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('flet'),
    hiddenimports=collect_submodules('flet'),
    hookspath=['.github/pyinstaller-hooks'],
    ...
)
```

### 2. .app Bundle 结构

```
open-daily-stock-gui.app/
└── Contents/
    ├── Info.plist          # 应用配置
    ├── MacOS/
    │   └── open-daily-stock-gui  # 可执行文件
    └── Resources/
        └── (资源文件)
```

**Info.plist 关键字段**:
- `CFBundleName`: open-daily-stock-gui
- `CFBundleDisplayName`: Open Daily Stock
- `CFBundleIdentifier`: com.opendailystock.gui
- `CFBundleVersion`: 0.3.6
- `CFBundleShortVersionString`: 0.3.6
- `LSMinimumSystemVersion`: 10.15
- `NSHighResolutionCapable`: true

### 3. DMG 创建

**工具**: `create-dmg` 或 `hdiutil`

**DMG 内容**:
- `open-daily-stock-gui.app` (拖拽到 Applications 提示)
- `Applications` 文件夹别名（可选）

**DMG 名称**: `open-daily-stock-gui-v0.3.6-macos.dmg`

### 4. 新增文件

| 文件 | 说明 |
|------|------|
| `scripts/package-macos-app.sh` | 打包脚本，生成 .app 和 DMG |
| `.github/workflows/release-dmg.yml` | CI 流程，tag 触发生成 DMG |

### 5. 脚本设计

**scripts/package-macos-app.sh**:

```bash
#!/bin/bash
set -e

VERSION=${1:-$(git describe --tags)}

# 1. PyInstaller 打包
cd gui
pyinstaller open-daily-stock.spec

# 2. 创建 .app 结构
APPNAME="open-daily-stock-gui.app"
CONTENTS="dist/$APPNAME/Contents"
mkdir -p "$CONTENTS/MacOS"
mkdir -p "$CONTENTS/Resources"

# 复制可执行文件
cp "dist/open-daily-stock-gui" "$CONTENTS/MacOS/"

# 复制 spec 中的 datas 到 Resources
# (可选：根据需要复制资源文件)

# 3. 创建 Info.plist
cat > "$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>open-daily-stock-gui</string>
    ...
</dict>
</plist>
EOF

# 4. 创建 DMG
create-dmg \
  --volname "Open Daily Stock" \
  --volicon "..." \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "open-daily-stock-gui.app" 200 150 \
  --hide-extension "open-daily-stock-gui.app" \
  --app-drop-link 400 150 \
  "dist/open-daily-stock-gui-$VERSION-macos.dmg" \
  "dist/$APPNAME"
```

### 6. CI 流程

**文件**: `.github/workflows/release-dmg.yml`

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
          pip install pyinstaller flet>=0.25.0
      - name: Install create-dmg
        run: brew install create-dmg
      - name: Run packaging script
        run: ./scripts/package-macos-app.sh ${{ github.ref_name }}
      - name: Upload DMG
        uses: actions/upload-artifact@v4
        with:
          name: open-daily-stock-gui-dmg
          path: dist/open-daily-stock-gui-*.dmg
```

## 依赖项

| 工具 | 安装方式 |
|------|----------|
| `create-dmg` | `brew install create-dmg` |
| PyInstaller | 已在 requirements.txt |
| flet | 已在 requirements.txt |

## 包体预估

- 可执行文件（PyInstaller 单文件）: ~80-120MB
- .app bundle: ~100-150MB
- DMG 镜像（压缩）: ~70-100MB

## 产出物

1. `dist/open-daily-stock-gui` - PyInstaller 打包的可执行文件
2. `dist/open-daily-stock-gui.app` - macOS App Bundle
3. `dist/open-daily-stock-gui-{VERSION}-macos.dmg` - DMG 安装包

## 已知限制

- macOS 10.15+ 支持
- Apple Silicon (M1/M2) 和 Intel 均支持
- 需要签署或允许"任何来源"运行（系统偏好设置）

## TODO

- [ ] 创建 `scripts/package-macos-app.sh` 打包脚本
- [ ] 添加 `.github/workflows/release-dmg.yml` CI 流程
- [ ] 测试本地打包生成 DMG
- [ ] CI 验证 DMG 生成成功
