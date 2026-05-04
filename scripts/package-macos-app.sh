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